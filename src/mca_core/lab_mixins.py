"""
实验室 Mixin 模块

提供诊断实验室功能，包括场景生成和全链路压测。

类说明:
    - LabMixin: 实验室功能 Mixin，处理对抗性测试和场景生成
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Optional

import tkinter as tk
from tkinter import scrolledtext, ttk

if TYPE_CHECKING:
    from tkinter import Tk
    from mca_core.learning import CrashPatternLearner

from config.constants import BASE_DIR, LAB_HEAD_READ_SIZE

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

try:
    from tools.generate_mc_log import generate_batch
    HAS_LOG_GENERATOR: bool = True
except ImportError:
    generate_batch = None
    HAS_LOG_GENERATOR = False

HAS_TORCH: bool = False

logger = logging.getLogger("mca_core.lab")


class LabMixin:
    """
    实验室功能 Mixin。
    
    提供对抗性测试场景生成和全链路压力测试功能。
    该 Mixin 假设宿主类具有以下属性:
        - auto_test_tab: 自动测试标签页容器
        - root: Tk 根窗口
        - crash_pattern_learner: CrashPatternLearner 实例 (可选)
    
    Attributes:
        lab_mode_var: 测试模式选择变量
        lab_count_var: 生成数量变量
        lab_status_var: 状态文本变量
        lab_running: 是否正在运行测试
        lab_log: 日志文本控件
    
    方法:
        - _create_auto_test_tab: 创建自动测试标签页
        - _log_lab: 记录测试日志
        - _run_lab_task: 执行实验室测试任务
    """

    lab_mode_var: tk.StringVar
    lab_count_var: tk.IntVar
    lab_status_var: tk.StringVar
    lab_running: bool
    lab_log: scrolledtext.ScrolledText
    auto_test_tab: Any
    root: Any
    crash_pattern_learner: Any

    SCENARIO_MAP: dict[str, str] = {
        "adversarial": "混合对抗",
        "oom": "内存溢出",
        "gl_error": "显存/渲染错误",
        "missing_dependency": "依赖缺失",
        "version_conflict": "版本冲突"
    }

    ATTACK_VECTORS: list[tuple[str, str]] = [
        ("混合对抗 (Adversarial)", "adversarial"),
        ("内存溢出 (OOM)", "oom"),
        ("显存/渲染 (GL Error)", "gl_error"),
        ("依赖缺失 (Dependency)", "missing_dependency"),
        ("版本冲突 (Version)", "version_conflict")
    ]

    def _create_auto_test_tab(self) -> None:
        """创建自动测试标签页。"""
        legacy_method = getattr(self, '_create_legacy_auto_test_tab', None)
        if legacy_method is not None and callable(legacy_method):
            legacy_method()
            return

        if not hasattr(self, 'auto_test_tab'):
            return

        try:
            for w in self.auto_test_tab.winfo_children():
                w.destroy()
        except Exception:
            pass

        main_frame = ttk.Frame(self.auto_test_tab, padding=10)
        main_frame.pack(fill="both", expand=True)

        if not HAS_LOG_GENERATOR:
            ttk.Label(
                main_frame,
                text="未检测到日志生成器 (tools/generate_mc_log.py)。",
                foreground="#c00"
            ).pack(anchor="w")
            return

        self._init_lab_vars()
        self._create_lab_header(main_frame)
        self._create_lab_control_panel(main_frame)
        self._create_lab_log(main_frame)
        self._bind_lab_events(main_frame)

    def _init_lab_vars(self) -> None:
        """初始化实验室变量。"""
        if not hasattr(self, "lab_mode_var"):
            self.lab_mode_var = tk.StringVar(value="adversarial")
            self.lab_count_var = tk.IntVar(value=5)
            self.lab_status_var = tk.StringVar(value="等待指令...")
            self.lab_running = False

    def _create_lab_header(self, parent: ttk.Frame) -> None:
        """
        创建实验室标题区域。
        
        Args:
            parent: 父容器
        """
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(
            header_frame,
            text="Diagnostics Lab",
            font=("Segoe UI", 16, "bold"),
            foreground="#2c3e50"
        ).pack(side="left")

        ttk.Label(
            header_frame,
            text=" | 场景生成与全链路压测",
            font=("Microsoft YaHei UI", 10),
            foreground="#7f8c8d"
        ).pack(side="left", padx=5, pady=(5, 0))

        status_frame = ttk.Frame(header_frame)
        status_frame.pack(side="right")

        ana_color = "#3498db"
        pattern_count = 0
        if hasattr(self, 'crash_pattern_learner') and self.crash_pattern_learner:
            pattern_count = self.crash_pattern_learner.get_pattern_count()
        ana_txt = f"蓝方 (Analyzer): 就绪 (库容量: {pattern_count})"
        ttk.Label(
            status_frame,
            text="⬤ " + ana_txt,
            foreground=ana_color,
            font=("Microsoft YaHei UI", 9, "bold")
        ).pack(side="right", padx=10)

    def _create_lab_control_panel(self, parent: ttk.Frame) -> None:
        """
        创建控制面板区域。
        
        Args:
            parent: 父容器
        """
        ctrl_frame = ttk.LabelFrame(parent, text="对抗生成控制台", padding=10)
        ctrl_frame.pack(fill="x", pady=(0, 10))

        self._create_vector_selection(ctrl_frame)
        self._create_intensity_control(ctrl_frame)
        self._create_action_button(ctrl_frame)

    def _create_vector_selection(self, parent: Any) -> None:
        """
        创建攻击向量选择区域。
        
        Args:
            parent: 父容器
        """
        ttk.Label(parent, text="攻击向量:").grid(row=0, column=0, sticky="w", pady=5)

        vec_frame = ttk.Frame(parent)
        vec_frame.grid(row=0, column=1, columnspan=3, sticky="w")

        for txt, val in self.ATTACK_VECTORS:
            ttk.Radiobutton(
                vec_frame,
                text=txt,
                variable=self.lab_mode_var,
                value=val
            ).pack(side="left", padx=5)

    def _create_intensity_control(self, parent: Any) -> None:
        """
        创建强度控制区域。
        
        Args:
            parent: 父容器
        """
        ttk.Label(parent, text="生成批次:").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Scale(
            parent,
            from_=1,
            to=50,
            variable=self.lab_count_var,
            orient="horizontal",
            length=200
        ).grid(row=1, column=1, sticky="w", padx=5)
        ttk.Label(parent, textvariable=self.lab_count_var).grid(row=1, column=2, sticky="w")

    def _create_action_button(self, parent: Any) -> None:
        """
        创建操作按钮。
        
        Args:
            parent: 父容器
        """
        def _run_lab_test() -> None:
            if self.lab_running:
                return
            self.lab_running = True
            threading.Thread(target=self._run_lab_task, daemon=True).start()

        btn = ttk.Button(
            parent,
            text="运行测试 (Inject Faults)",
            command=_run_lab_test
        )
        btn.grid(row=1, column=3, padx=20, sticky="e")

    def _create_lab_log(self, parent: ttk.Frame) -> None:
        """
        创建日志显示区域。
        
        Args:
            parent: 父容器
        """
        log_frame = ttk.LabelFrame(parent, text="测试运行日志", padding=10)
        log_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.lab_log = scrolledtext.ScrolledText(
            log_frame,
            height=12,
            state="disabled",
            font=("Consolas", 9),
            background="#000000",
            foreground="#00ff00"
        )
        self.lab_log.pack(fill="both", expand=True)

        self._configure_log_tags()

    def _configure_log_tags(self) -> None:
        """配置日志标签样式。"""
        self.lab_log.tag_config("system", foreground="#bdc3c7")
        self.lab_log.tag_config("adv", foreground="#e74c3c")
        self.lab_log.tag_config("def", foreground="#3498db")
        self.lab_log.tag_config("success", foreground="#2ecc71")
        self.lab_log.tag_config("fail", foreground="#e67e22")

    def _bind_lab_events(self, parent: ttk.Frame) -> None:
        """
        绑定实验室事件。
        
        Args:
            parent: 父容器
        """
        def _on_mousewheel(event: Any) -> None:
            self.lab_log.yview_scroll(int(-1 * (event.delta / 120)), "units")

        parent.bind_all("<MouseWheel>", _on_mousewheel)

    def _log_lab(self, msg: str, tag: str = "system") -> None:
        """
        记录测试日志。
        
        Args:
            msg: 日志消息
            tag: 日志标签 (system, adv, def, success, fail)
        """
        if not hasattr(self, 'lab_log'):
            return
        if hasattr(self, 'root'):
            self.root.after(0, lambda: self._log_lab_safe(msg, tag))

    def _log_lab_safe(self, msg: str, tag: str) -> None:
        """
        线程安全地记录日志。
        
        Args:
            msg: 日志消息
            tag: 日志标签
        """
        try:
            self.lab_log.config(state="normal")
            ts = datetime.now().strftime("%H:%M:%S")
            self.lab_log.insert(tk.END, f"[{ts}] {msg}\n", tag)
            self.lab_log.see(tk.END)
            self.lab_log.config(state="disabled")
        except Exception:
            pass

    def _run_lab_task(self) -> None:
        """执行实验室测试任务。"""
        scenario = self.lab_mode_var.get()
        count = self.lab_count_var.get()
        out_dir = os.path.join(BASE_DIR, "analysis_data", "lab_runs")

        scenario_cn = self.SCENARIO_MAP.get(scenario, scenario)

        self._log_lab(f"启动对抗生成引擎... 目标: {scenario_cn}, 数量: {count}", "adv")

        try:
            summary = self._generate_scenarios(out_dir, scenario, count)
            if summary is None:
                return

            self._log_lab(f"生成完成。共 {len(summary)} 个样本。", "adv")
            success_count = self._analyze_scenarios(summary, count)
            self._log_lab(f"对抗测试结束. 成功防御率: {success_count}/{count}", "system")

        except Exception as e:
            self._log_lab(f"运行时错误: {e}", "fail")
        finally:
            self.lab_running = False

    def _generate_scenarios(
        self,
        out_dir: str,
        scenario: str,
        count: int
    ) -> Optional[list[dict[str, Any]]]:
        """
        生成测试场景。
        
        Args:
            out_dir: 输出目录
            scenario: 场景类型
            count: 生成数量
            
        Returns:
            生成的场景摘要列表
        """
        if generate_batch is None:
            self._log_lab("错误: 日志生成器不可用。", "fail")
            return None

        return generate_batch(
            output_dir=out_dir,
            target_bytes=512 * 1024,
            seed=None,
            scenarios=[scenario],
            count=count,
            report_path=None
        )

    def _analyze_scenarios(
        self,
        summary: list[dict[str, Any]],
        total_count: int
    ) -> int:
        """
        分析生成的场景。
        
        Args:
            summary: 场景摘要列表
            total_count: 总数量
            
        Returns:
            成功分析的数量
        """
        try:
            from mca_core.idle_trainer import HeadlessAnalyzer
        except ImportError:
            self._log_lab("错误: 找不到 HeadlessAnalyzer 模块。", "fail")
            return 0

        self._warmup_analyzer()
        return self._run_parallel_analysis(summary, total_count, HeadlessAnalyzer)

    def _warmup_analyzer(self) -> None:
        """预热分析器组件。"""
        try:
            self._log_lab("核心组件预热中...", "def")
            from mca_core.idle_trainer import HeadlessAnalyzer
            warmup = HeadlessAnalyzer(None, head_only=True)
            del warmup
        except Exception as e:
            logger.warning(f"预热失败: {e}")

    def _run_parallel_analysis(
        self,
        summary: list[dict[str, Any]],
        total_count: int,
        HeadlessAnalyzer: type
    ) -> int:
        """
        并行分析场景。
        
        Args:
            summary: 场景摘要列表
            total_count: 总数量
            HeadlessAnalyzer: 分析器类
            
        Returns:
            成功分析的数量
        """
        max_workers = os.cpu_count() or 4
        self._log_lab(f"启动并行分析 (线程数: {max_workers})...", "def")

        success_count = 0
        learner = getattr(self, 'crash_pattern_learner', None)

        def _analyze_worker(
            idx: int,
            item: dict[str, Any],
            learner_instance: Optional[Any]
        ) -> tuple[int, str, bool, dict[str, int], list[str]]:
            f_path = item["file"]
            f_name = os.path.basename(f_path)
            analyzer = HeadlessAnalyzer(learner_instance, max_bytes=LAB_HEAD_READ_SIZE, head_only=True)
            found = analyzer.run_cycle(f_path)
            return idx, f_name, found, dict(analyzer.cause_counts), analyzer.analysis_results

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for i, item in enumerate(summary):
                futures.append(
                    executor.submit(_analyze_worker, i + 1, item, learner)
                )

            for future in as_completed(futures):
                try:
                    idx, fname, is_success, causes, details = future.result()
                    if is_success:
                        self._log_analysis_success(idx, total_count, fname, causes, details)
                        success_count += 1
                    else:
                        self._log_lab(f"[{idx}/{total_count}] {fname} -> 拦截失败!", "fail")
                except Exception as exc:
                    self._log_lab(f"分析异常: {exc}", "fail")

        return success_count

    def _log_analysis_success(
        self,
        idx: int,
        total: int,
        fname: str,
        causes: dict[str, int],
        details: list[str]
    ) -> None:
        """
        记录分析成功日志。
        
        Args:
            idx: 序号
            total: 总数
            fname: 文件名
            causes: 原因计数
            details: 详细信息
        """
        if causes:
            cause_str = ", ".join([f"{k}x{v}" for k, v in causes.items()])
            self._log_lab(f"[{idx}/{total}] {fname} -> 拦截成功! ({cause_str})", "success")
        else:
            self._log_lab(f"[{idx}/{total}] {fname} -> 拦截成功! (未知归类)", "success")

        if details:
            self._log_analysis_details(details)

    def _log_analysis_details(self, details: list[str]) -> None:
        """
        记录分析详情。
        
        Args:
            details: 详细信息列表
        """
        display_lines = []
        skip_keywords = ["扫描完成", "Mod总数", "加载器:"]

        for d in details:
            d = d.rstrip()
            if not d:
                continue
            if any(skip in d for skip in skip_keywords):
                continue
            display_lines.append(d)

        max_show = 8
        for i, line in enumerate(display_lines):
            if i >= max_show:
                self._log_lab(f"      ... (还有 {len(display_lines) - max_show} 条详情)", "def")
                break

            clean_line = line.strip()
            if clean_line.startswith("-") or line.startswith("  "):
                self._log_lab(f"      {clean_line}", "def")
            else:
                self._log_lab(f"    > {clean_line}", "def")
