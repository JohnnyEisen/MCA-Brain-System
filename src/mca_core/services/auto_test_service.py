"""
自动测试服务模块。

负责批量生成崩溃日志并运行训练分析，验证诊断准确率。
从 app.py 提取，实现业务逻辑与 UI 解耦。
"""

import os
import time
import threading
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, List, Any, Tuple
from collections import Counter, defaultdict

from config.constants import (
    BASE_DIR,
    LAB_HEAD_READ_SIZE,
    CAUSE_MEM,
    CAUSE_DEP,
    CAUSE_VER,
    CAUSE_GPU,
    CAUSE_OTHER,
)
from mca_core.security import InputSanitizer
from mca_core.file_io import read_text_head
from mca_core.threading_utils import submit_task


@dataclass
class AutoTestConfig:
    """自动测试配置。"""
    target_bytes: int = 2 * 1024 * 1024  # 2MB
    count: int = 10
    seed: Optional[int] = None
    scenarios: List[str] = field(default_factory=lambda: ["normal"])
    output_dir: str = ""
    report_path: Optional[str] = None
    train: bool = True
    isolated: bool = False
    max_single_size: Optional[int] = None


@dataclass
class AutoTestSummary:
    """自动测试结果摘要。"""
    generated: int = 0
    trained: int = 0
    samples: int = 0
    gen_time: float = 0.0
    train_time: float = 0.0
    total_time: float = 0.0
    hit_rate: float = 0.0
    fp_rate: float = 0.0
    report: Optional[str] = None


class AutoTestService:
    """
    自动化测试服务。
    
    负责批量生成崩溃日志样本，运行诊断分析，并评估准确率。
    通过回调机制与 UI 解耦。
    """
    
    def __init__(
        self,
        run_analysis_callback: Callable[[str, str, Any], Optional[Dict]],
        log_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        ui_schedule_callback: Optional[Callable[[Callable], None]] = None,
    ):
        """
        初始化自动测试服务。
        
        Args:
            run_analysis_callback: 执行分析的回调，签名 (log_text, file_path, learner) -> result_dict
            log_callback: 日志输出回调，签名 (message) -> None
            progress_callback: 进度更新回调，签名 (value, status) -> None
            ui_schedule_callback: UI 线程调度回调，签名 (func) -> None
        """
        self._run_analysis = run_analysis_callback
        self._log = log_callback or print
        self._progress = progress_callback
        self._schedule_ui = ui_schedule_callback
        
        self._cancel_event = threading.Event()
        self._running = False
        self._last_summary: Optional[AutoTestSummary] = None
        
        # 延迟导入，避免启动时依赖
        self._generate_batch = None
        self._parse_size = None
        self._has_generator = False
        self._try_import_generator()
    
    def _try_import_generator(self):
        """尝试导入日志生成器。"""
        try:
            from tools.generate_mc_log import generate_batch, parse_size
            self._generate_batch = generate_batch
            self._parse_size = parse_size
            self._has_generator = True
        except ImportError:
            self._has_generator = False
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    @property
    def last_summary(self) -> Optional[AutoTestSummary]:
        return self._last_summary
    
    def has_generator(self) -> bool:
        """检查是否有日志生成器可用。"""
        return self._has_generator
    
    def start(self, config: AutoTestConfig, learner: Any = None) -> bool:
        """
        启动自动测试。
        
        Args:
            config: 测试配置
            learner: CrashPatternLearner 实例（可选）
            
        Returns:
            是否成功启动
        """
        if not self._has_generator:
            self._log("错误: 日志生成器不可用")
            return False
        
        if self._running:
            self._log("警告: 测试已在运行中")
            return False
        
        # 验证输出目录
        output_dir = config.output_dir or os.path.join(BASE_DIR, "analysis_data", "auto_tests")
        if not InputSanitizer.validate_dir_path(output_dir, create=True):
            self._log(f"错误: 输出目录路径非法或不可写: {output_dir}")
            return False
        
        self._cancel_event.clear()
        self._running = True
        
        submit_task(self._worker, config, learner)
        
        return True
    
    def stop(self):
        """请求停止测试。"""
        self._cancel_event.set()
        self._log("正在停止测试...")
    
    def _worker(self, config: AutoTestConfig, learner: Any):
        """后台工作线程。"""
        try:
            self._log(f"生成日志：{config.count} 份，场景: {', '.join(config.scenarios)}")
            self._update_progress(0, "生成中")
            
            t0 = time.time()
            
            def progress_cb(stage, idx, total, file_path, scenario):
                if stage == "generate":
                    self._log(f"[{idx}/{total}] 生成: {os.path.basename(file_path)} (场景 {scenario})")
                    self._update_progress(idx / max(total, 1) * 0.3, "生成中")
            
            summary_list = self._generate_batch(
                config.output_dir,
                config.target_bytes,
                config.seed,
                config.scenarios,
                config.count,
                config.report_path,
                progress_cb=progress_cb,
                cancel_cb=lambda: self._cancel_event.is_set(),
                max_single_size=config.max_single_size,
            ) if self._generate_batch else []
            
            if summary_list is None:
                summary_list = []
            
            gen_time = time.time() - t0
            self._log(f"生成完成，共 {len(summary_list)} 份日志")
            
            if not config.train:
                self._last_summary = AutoTestSummary(
                    generated=len(summary_list),
                    gen_time=gen_time,
                    total_time=gen_time,
                    report=config.report_path,
                )
                self._finish()
                return
            
            # 训练阶段
            self._update_progress(0.3, "训练中")
            t1 = time.time()
            train_time_acc = 0.0
            hit_count = 0
            fp_count = 0
            eval_count = 0
            
            # 选择学习器
            if config.isolated:
                synth_path = os.path.join(BASE_DIR, "analysis_data", "learned_patterns_synth.json")
                try:
                    from mca_core.learning import CrashPatternLearner
                    active_learner = CrashPatternLearner(synth_path)
                except Exception:
                    active_learner = learner
            else:
                active_learner = learner
            
            for idx, item in enumerate(summary_list):
                if self._cancel_event.is_set():
                    self._log("已请求停止，训练中止")
                    break
                
                file_path = item.get("file")
                if not file_path:
                    continue
                
                try:
                    log_text = read_text_head(file_path, max_bytes=LAB_HEAD_READ_SIZE)
                except Exception:
                    self._log(f"读取失败: {file_path}")
                    continue
                
                self._log(f"[{idx+1}/{len(summary_list)}] 训练: {os.path.basename(file_path)}")
                
                s0 = time.perf_counter()
                result = self._run_analysis(log_text, file_path, active_learner)
                train_time_acc += (time.perf_counter() - s0)
                
                scenario = item.get("scenario")
                if scenario:
                    hit, fp = self._score_result(scenario, result)
                    self._log(f"[{idx+1}] 评分: hit={hit}, fp={fp}")
                    if hit:
                        hit_count += 1
                    if fp:
                        fp_count += 1
                else:
                    self._log(f"[{idx+1}] 缺少场景标签，跳过评分")
                
                eval_count += 1
                progress = 0.3 + (idx + 1) / max(len(summary_list), 1) * 0.7
                self._update_progress(progress, "训练中")
            
            train_time = max(train_time_acc, time.time() - t1, 0.001)
            total_time = time.time() - t0
            
            hit_rate = hit_count / max(eval_count, 1)
            fp_rate = fp_count / max(eval_count, 1)
            
            self._log(f"评分汇总: hit={hit_count}, fp={fp_count}, samples={eval_count}")
            
            self._last_summary = AutoTestSummary(
                generated=len(summary_list),
                trained=len(summary_list),
                samples=eval_count,
                gen_time=gen_time,
                train_time=train_time,
                total_time=total_time,
                hit_rate=hit_rate,
                fp_rate=fp_rate,
                report=config.report_path,
            )
            
            # 自动清理
            self._cleanup_files(summary_list)
            
        except Exception as e:
            self._log(f"自动化测试失败: {e}")
        finally:
            self._finish()
    
    def _finish(self):
        """完成测试。"""
        self._running = False
        self._update_progress(1.0, "已完成")
        self._log("自动化测试完成")
        
        if self._last_summary:
            self._show_summary(self._last_summary)
    
    def _cleanup_files(self, summary_list: List[Dict], cleanup: bool = True):
        """清理生成的文件。"""
        if not cleanup:
            return
        
        self._log("正在清理生成的文件...")
        cnt = 0
        for item in summary_list:
            try:
                fp = item.get("file")
                if fp and os.path.exists(fp):
                    os.remove(fp)
                    cnt += 1
            except Exception:
                pass
        self._log(f"清理完成，删除了 {cnt} 个文件。")
    
    def _update_progress(self, value: float, status: str):
        """更新进度。"""
        progress_cb = self._progress
        if progress_cb:
            if self._schedule_ui:
                self._schedule_ui(lambda: progress_cb(value, status))
            else:
                progress_cb(value, status)
    
    def _show_summary(self, summary: AutoTestSummary):
        """显示测试摘要。"""
        msg = (
            f"===== 自动化测试总结 =====\n"
            f"生成日志: {summary.generated}\n"
            f"训练样本: {summary.samples}\n"
            f"命中率: {summary.hit_rate:.0%}\n"
            f"误报率: {summary.fp_rate:.0%}\n"
            f"生成耗时: {summary.gen_time:.2f}s\n"
            f"训练耗时: {summary.train_time:.2f}s\n"
            f"总耗时: {summary.total_time:.2f}s\n"
        )
        if summary.report:
            msg += f"报告: {summary.report}\n"
        msg += "========================"
        self._log(msg)
    
    def _score_result(self, scenario: str, result: Optional[Dict]) -> Tuple[bool, bool]:
        """
        评分分析结果。
        
        Args:
            scenario: 场景名称
            result: 分析结果字典
            
        Returns:
            (hit, false_positive) 元组
        """
        if result is None:
            return False, False
        
        texts = "\n".join(result.get("analysis_results", [])).lower()
        causes = result.get("cause_counts", {}) or {}
        
        indicators = {
            "oom": ["outofmemory", "内存", "heap"],
            "missing_dependency": ["missing mod", "missing or unsupported", "依赖", "requires", "缺失"],
            "gl_error": ["opengl", "glfw", "gl ", "渲染"],
            "mixin_conflict": ["mixin", "混入", "conflict", "incompatible"],
            "version_conflict": ["版本", "version", "incompatible"],
            "compound": ["outofmemory", "missing mod", "mixin", "opengl", "版本", "依赖"],
        }
        
        cause_expect = {
            "oom": CAUSE_MEM,
            "missing_dependency": CAUSE_DEP,
            "version_conflict": CAUSE_VER,
            "gl_error": CAUSE_GPU,
            "compound": CAUSE_OTHER,
            "mixin_conflict": CAUSE_OTHER,
        }
        
        if scenario == "normal":
            error_keywords = [
                "outofmemory", "missing mod", "mixin", "opengl", "glfw", "版本", "依赖", "错误", "崩溃"
            ]
            false_positive = any(k in texts for k in error_keywords)
            if any(v > 0 for v in causes.values()):
                false_positive = True
            return False, false_positive
        
        keys = indicators.get(scenario, [])
        hit = any(k in texts for k in keys)
        expected_cause = cause_expect.get(scenario)
        if expected_cause and causes.get(expected_cause, 0) > 0:
            hit = True
        return hit, False
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """格式化持续时间。"""
        try:
            if seconds < 1:
                ms = max(int(seconds * 1000), 1)
                return f"{ms}ms"
            return f"{seconds:.2f}s"
        except Exception:
            return "-"
    
    @staticmethod
    def parse_size(size_str: str) -> int:
        """解析大小字符串（如 '2MB', '512KB'）为字节数。"""
        size_str = size_str.strip().upper()
        multipliers = {
            "KB": 1024,
            "MB": 1024 * 1024,
            "GB": 1024 * 1024 * 1024,
        }
        
        for suffix, mult in multipliers.items():
            if size_str.endswith(suffix):
                try:
                    return int(float(size_str[:-len(suffix)]) * mult)
                except ValueError:
                    pass
        
        try:
            return int(size_str)
        except ValueError:
            return 2 * 1024 * 1024  # 默认 2MB
