"""
分析逻辑 Mixin 模块

提供核心分析逻辑，包括缓存管理、检测器执行和学习引擎集成。

模块说明:
    本模块实现了崩溃日志分析的核心逻辑，通过 Mixin 模式为主应用提供分析功能。
    
    主要组件:
        - AnalysisMixinHost: 分析器宿主接口协议
        - AnalysisMixin: 分析逻辑 Mixin 类

架构设计:
    - 使用 Protocol 定义宿主类接口，实现静态类型检查
    - 支持 LRU 缓存避免重复分析相同日志
    - 支持检测器并行执行提升性能
    - 集成智能学习引擎提供 AI 辅助诊断
"""

from __future__ import annotations

import copy
import csv
import logging
import os
import sys
import threading
from collections import defaultdict, Counter, OrderedDict
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import tkinter as tk
from tkinter import messagebox
import tkinter.ttk as ttk

if TYPE_CHECKING:
    from mca_core.plugins import PluginRegistry
    from mca_core.detectors import DetectorRegistry
    from mca_core.services.database import DatabaseManager
    from config.app_config import AppConfig

from mca_core.regex_cache import RegexCache
from mca_core.errors import TaskCancelledError
from mca_core.threading_utils import submit_task
from mca_core.history_manager import append_history
from config.constants import HISTORY_FILE, BASE_DIR

logger = logging.getLogger(__name__)


# ============================================================
# 宿主协议定义 - Host Protocol Definition
# ============================================================

@runtime_checkable
class AnalysisMixinHost(Protocol):
    """
    分析器宿主接口协议。
    
    定义 AnalysisMixin 需要宿主类提供的方法和属性。
    使用 @runtime_checkable 允许运行时类型检查。
    """
    
    root: tk.Tk
    lock: threading.RLock
    status_var: tk.StringVar
    crash_log: str
    file_path: str
    file_checksum: str
    analysis_results: list[str]
    mods: dict[str, set]
    dependency_pairs: set[tuple[str, str]]
    loader_type: str | None
    cause_counts: Counter
    plugin_registry: "PluginRegistry"
    detector_registry: "DetectorRegistry"
    database_manager: "DatabaseManager"
    crash_pattern_learner: Any
    brain: Any
    HAS_NEW_MODULES: bool
    progress: ttk.Progressbar
    result_text: tk.Text
    app_config: "AppConfig | None"
    progress_reporter: Any
    task_executor: Any
    diagnostic_engine: Any
    _cancel_event: threading.Event
    _cache_hit: bool
    _analysis_cache: OrderedDict
    _analysis_cache_ordered: bool
    _graph_cache_key: Any
    _graph_rendered: bool
    _cache_max_size: int
    
    def _reload_config_if_changed(self) -> None: ...
    def _is_cancelled(self) -> bool: ...
    def _clean_modid(self, raw: str) -> str: ...
    def display_results(self) -> None: ...
    def update_dependency_graph(self) -> None: ...
    def update_cause_chart(self) -> None: ...
    def _start_ai_init_if_needed(self) -> None: ...
    def _extract_dependency_pairs(self) -> None: ...
    def _auto_test_write_log(self, msg: str) -> None: ...
    def _report_progress(self, val: float, msg: str) -> None: ...
    def _run_analysis_thread(self) -> None: ...
    def _detect_loader(self) -> str: ...
    def _extract_mods(self) -> None: ...
    def _run_detectors(self) -> None: ...
    def _run_smart_diagnostics(self) -> None: ...
    def _run_dependency_analysis(self) -> None: ...
    def _run_learning_based_analysis(self) -> None: ...
    def _build_precise_summary(self) -> None: ...
    def _clean_dependency_pairs(self) -> None: ...
    def _run_analysis_logic(self) -> None: ...
    def _record_history(self) -> None: ...
    def _post_analysis_ui_update(self, cached: bool) -> None: ...


# ============================================================
# 分析逻辑 Mixin - Analysis Logic Mixin
# ============================================================

class AnalysisMixin:
    """
    核心分析逻辑 Mixin。
    
    提供崩溃日志分析的核心功能，包括:
    - LRU 缓存管理
    - 模组信息提取
    - 检测器执行
    - 智能学习引擎集成
    - 历史记录管理
    
    Attributes:
        root: Tkinter 根窗口
        lock: 线程锁
        status_var: 状态变量
        crash_log: 崩溃日志文本
        file_path: 文件路径
        file_checksum: 文件校验和
        analysis_results: 分析结果列表
        mods: 模组字典
        dependency_pairs: 依赖关系对
        loader_type: 加载器类型
        cause_counts: 崩溃原因计数器
    
    方法:
        - start_analysis: 启动分析流程
        - _run_analysis_logic: 核心分析逻辑（带缓存）
        - add_cause: 添加崩溃原因
        - _extract_mods: 提取模组信息
        - _run_detectors: 执行检测器
        - display_results: 显示分析结果
    """
    
    root: tk.Tk
    lock: threading.RLock
    status_var: tk.StringVar
    crash_log: str
    file_path: str
    file_checksum: str
    analysis_results: list[str]
    mods: dict[str, set]
    dependency_pairs: set[tuple[str, str]]
    loader_type: str | None
    cause_counts: Counter
    plugin_registry: "PluginRegistry"
    detector_registry: "DetectorRegistry"
    database_manager: "DatabaseManager"
    crash_pattern_learner: Any
    brain: Any
    HAS_NEW_MODULES: bool
    progress: ttk.Progressbar
    result_text: tk.Text
    app_config: "AppConfig | None"
    progress_reporter: Any
    task_executor: Any
    _analysis_cache: OrderedDict
    diagnostic_engine: Any
    _cancel_event: threading.Event
    _cache_hit: bool
    _analysis_cache_ordered: bool
    _graph_cache_key: Any
    _graph_rendered: bool
    _cache_max_size: int

    def start_analysis(self: AnalysisMixinHost) -> None:
        """
        启动崩溃日志分析流程。
        
        检查前置条件，启动后台分析任务。
        """
        self._reload_config_if_changed()
        if not self.crash_log:
            messagebox.showinfo("提示", "请先加载崩溃日志文件。")
            return
        if getattr(self, "_is_auto_testing", False):
            messagebox.showwarning("忙碌", "自动化测试正在运行中，请等待其完成或停止后再试。")
            return
        if not hasattr(self, '_cancel_event'):
            self._cancel_event = threading.Event()
        self._cancel_event.clear()
        self.progress.pack(fill="x", padx=10, pady=(4, 6))
        self.progress.config(mode="indeterminate")
        self.progress.start(10)
        self.status_var.set("正在分析...")
        if hasattr(self, 'task_executor') and self.task_executor:
            self.task_executor.submit_analysis_task(self._run_analysis_thread, lambda r: None)
        else:
            submit_task(self._run_analysis_thread)

    def _report_progress(self: AnalysisMixinHost, val: float, msg: str = "") -> None:
        """
        报告分析进度。
        
        Args:
            val: 进度值 (0.0 - 1.0)
            msg: 进度消息
        """
        if getattr(self, "_is_auto_testing", False):
            return
        self.root.after(0, lambda: self.status_var.set(msg))
        if hasattr(self, 'progress_reporter'):
            self.progress_reporter.report(val, msg)

    def _run_analysis_logic(self: AnalysisMixinHost) -> None:
        """
        核心分析逻辑（带 LRU 缓存）。
        
        执行完整的分析流程，包括:
        1. 缓存检查
        2. 加载器检测
        3. 模组提取
        4. 检测器执行
        5. 智能诊断
        6. 摘要生成
        7. 缓存写入
        """
        logger.info("[ANALYSIS] _run_analysis_logic started")
        self._cache_hit = False
        
        if self.file_checksum:
            with self.lock:
                cached = self._analysis_cache.get(self.file_checksum)
            if cached:
                logger.info("[ANALYSIS] Cache hit, skipping analysis")
                self.analysis_results[:] = cached['results']
                self.mods = defaultdict(set, {k: set(v) for k, v in cached['mods'].items()})
                self.dependency_pairs = set(cached['dep_pairs'])
                self.loader_type = cached['loader']
                self.cause_counts.clear()
                self.cause_counts.update(cached['causes'])
                self._cache_hit = True
                self._report_progress(1.0, "分析完成 (缓存命中)")
                return
        
        logger.info("[ANALYSIS] Cache miss, starting full analysis")
        
        if self._is_cancelled(): 
            raise TaskCancelledError
        logger.debug("[ANALYSIS] Detecting loader")
        self.loader_type = self._detect_loader()
        self._report_progress(1/6, "检测加载器")
        if self._is_cancelled(): 
            raise TaskCancelledError
        logger.debug("[ANALYSIS] Extracting mods")
        self._extract_mods()
        self._report_progress(2/6, "提取 Mod 信息")
        if self._is_cancelled(): 
            raise TaskCancelledError
        logger.info("[ANALYSIS] Running detectors")
        self._run_detectors()
        logger.info("[ANALYSIS] Detectors complete")
        self._report_progress(3/6, "执行检测器")
        if self._is_cancelled(): 
            raise TaskCancelledError
        if self.HAS_NEW_MODULES:
            self._run_smart_diagnostics()
            self._run_dependency_analysis()
        if getattr(self, "app_config", None) and getattr(self.app_config, "enable_smart_learning", False):
            self._run_learning_based_analysis()
        self._report_progress(4/6, "智能诊断")
        self._build_precise_summary()
        self._report_progress(5/6, "生成摘要")
        self.analysis_results = list(dict.fromkeys(self.analysis_results))
        self._clean_dependency_pairs()
        if self.crash_pattern_learner:
            try:
                self.crash_pattern_learner.learn_from_crash(self.crash_log, self.analysis_results)
            except Exception as e:
                logger.warning(f"智能学习记录失败: {e}")
        disabled_plugins = getattr(self, "_disabled_plugins", set())
        for plugin in self.plugin_registry.list():
            plugin_key = f"{getattr(plugin, '__module__', 'unknown')}:{getattr(plugin, '__name__', 'plugin_entry')}"
            if plugin_key in disabled_plugins:
                continue
            try: 
                plugin(self)
            except Exception as e: 
                logger.warning(f"插件 {plugin} 执行异常: {e}")
        
        if self.file_checksum:
            with self.lock:
                max_size = getattr(self, '_cache_max_size', 100)
                
                if not hasattr(self, '_analysis_cache_ordered'):
                    from collections import OrderedDict
                    self._analysis_cache = OrderedDict(self._analysis_cache)
                    self._analysis_cache_ordered = True
                
                if self.file_checksum in self._analysis_cache:
                    self._analysis_cache.move_to_end(self.file_checksum)
                else:
                    while len(self._analysis_cache) >= max_size:
                        self._analysis_cache.popitem(last=False)
                    
                    mods_light = {k: list(v) for k, v in self.mods.items()} if self.mods else {}
                    self._analysis_cache[self.file_checksum] = {
                        'results': list(self.analysis_results),
                        'mods': mods_light,
                        'dep_pairs': frozenset(self.dependency_pairs),
                        'loader': self.loader_type,
                        'causes': dict(self.cause_counts)
                    }

    def add_cause(self: AnalysisMixinHost, cause_label: str) -> None:
        """
        添加崩溃原因计数。
        
        Args:
            cause_label: 崩溃原因标签
        """
        with self.lock:
            self.cause_counts[cause_label] += 1

    def _extract_mods(self: AnalysisMixinHost) -> None:
        """
        从崩溃日志中提取模组信息。
        
        使用正则表达式匹配模组 JAR 文件名。
        """
        self.mods = defaultdict(set)
        text = self.crash_log or ""
        pattern = r"(?:^|[\/\\])([a-zA-Z0-9_\-]+)-(\d[\w\.\-]+)\.jar"
        seen = set()
        for m in RegexCache.finditer(pattern, text):
            raw_id, ver = m.groups()
            modid = self._clean_modid(raw_id)
            if modid and modid not in seen:
                self.mods[modid].add(ver)
                seen.add(f"{modid}:{ver}")
        self.analysis_results.append(f"扫描完成：发现 {len(self.mods)} 个模组文件。")

    def _run_detectors(self: AnalysisMixinHost) -> None:
        """
        执行所有注册的检测器。
        
        使用 Brain System 线程池加速执行（如果可用）。
        """
        self._extract_dependency_pairs()
        executor = None
        if self.brain:
            executor = self.brain.thread_pool
            logger.info("Using Brain System for detector acceleration")
        workers = os.cpu_count() or 4
        workers = min(workers, 8)
        detectors_list = self.detector_registry.list()
        if hasattr(self, "_auto_test_write_log"):
            self._auto_test_write_log(f"执行检测器: count={len(detectors_list)}, workers={workers}")
        self.detector_registry.run_all_parallel(self, max_workers=workers, executor=executor)

    def _run_analysis_thread(self: AnalysisMixinHost) -> None:
        """
        后台分析线程入口。
        
        处理缓存和 UI 更新。
        """
        try:
            self.analysis_results.clear()
            self.cause_counts.clear()
            self._graph_cache_key = None
            self._graph_rendered = False
            
            self._run_analysis_logic()
            
            self._record_history()
            self._report_progress(1.0, "分析完成")
            self._post_analysis_ui_update(cached=getattr(self, '_cache_hit', False))
        except TaskCancelledError:
            self.analysis_results.append(">> 分析操作已由用户取消。")
            self._report_progress(0, "已取消")
            self.root.after(0, self.display_results)
        except Exception:
            logger.exception("分析过程发生不可预期的错误")
            self.analysis_results.append(f"分析出错: {sys.exc_info()[1]}")
            self._report_progress(0, "分析出错")
            self.root.after(0, self.display_results)
        finally:
            self.root.after(0, self.progress.stop)
            self.root.after(0, lambda: self.progress.pack_forget())

    def _post_analysis_ui_update(self: AnalysisMixinHost, cached: bool) -> None:
        """
        分析完成后的 UI 更新。
        
        Args:
            cached: 是否命中缓存
        """
        self.root.after(0, self.display_results)
        delay = 100 if cached else 300
        self.root.after(delay, self.update_dependency_graph)
        self.root.after(delay, lambda: submit_task(self.update_cause_chart))

    def _detect_loader(self: AnalysisMixinHost) -> str:
        """
        检测崩溃日志中的模组加载器类型。
        
        Returns:
            加载器类型字符串 (NeoForge/Forge/Fabric/Quilt/Unknown)
        """
        txt = (self.crash_log or "").lower()
        if "neoforge" in txt: 
            return "NeoForge"
        if "forge" in txt and "fml" in txt: 
            return "Forge"
        if "fabric loader" in txt or ("fabric" in txt and "quilt" not in txt): 
            return "Fabric"
        if "quilt" in txt: 
            return "Quilt"
        return "Unknown"

    def _clean_dependency_pairs(self: AnalysisMixinHost) -> None:
        """清理无效的依赖关系对。"""
        if not self.dependency_pairs: 
            return
        self.dependency_pairs = {(p, c) for p, c in self.dependency_pairs if p and c and p != c}

    def _extract_dependency_pairs(self: AnalysisMixinHost) -> None:
        """
        从崩溃日志中提取模组依赖关系。
        
        支持多种格式的依赖声明。
        """
        text = self.crash_log or ""
        p1 = r"Missing mod '([^']+)' needed by '([^']+)'"
        for m in RegexCache.finditer(p1, text):
            self.dependency_pairs.add((m.group(2), m.group(1)))
            self.analysis_results.append(f"发现依赖关系: {m.group(2)} -> {m.group(1)} (缺失)")
        p2 = r"Mod ([^ ]+) requires ([^ \n]+)"
        for m in RegexCache.finditer(p2, text):
            self.dependency_pairs.add((m.group(1), m.group(2)))

    def _run_smart_diagnostics(self: AnalysisMixinHost) -> None:
        """
        运行智能诊断引擎。
        
        使用诊断引擎分析崩溃日志并提供建议。
        """
        if self.diagnostic_engine and self.HAS_NEW_MODULES:
            res = self.diagnostic_engine.analyze(self.crash_log)
            if res:
                self.analysis_results.append(">> 智能诊断建议:")
                self.analysis_results.extend([f" - {r}" for r in res])

    def _run_learning_based_analysis(self: AnalysisMixinHost) -> None:
        """
        运行基于学习的分析。
        
        使用模式学习器提供 AI 辅助诊断。
        """
        if not self.crash_pattern_learner: 
            return
        self._start_ai_init_if_needed()
        try:
            suggestions = self.crash_pattern_learner.suggest_solutions(self.crash_log)
            if suggestions:
                self.analysis_results.append(">> 智能学习引擎建议:")
                for s in suggestions:
                    self.analysis_results.append(f" - {s.text}")
        except Exception as e:
            logger.warning(f"智能学习分析执行出错: {e}")

    def _run_dependency_analysis(self: AnalysisMixinHost) -> None:
        """运行依赖分析（可扩展占位符）。"""
        pass

    def _build_precise_summary(self: AnalysisMixinHost) -> None:
        """
        构建精确的分析摘要。
        
        在结果列表开头插入加载器和模组统计信息。
        """
        summary = [
            f"加载器: {self.loader_type.upper() if self.loader_type else '未知'}",
            f"Mod总数: {len(self.mods)}"
        ]
        self.analysis_results[0:0] = summary

    def _record_history(self: AnalysisMixinHost) -> None:
        """
        记录分析历史。
        
        使用统一的历史管理器保存分析记录。
        """
        try:
            summary = "; ".join(self.analysis_results[:6])[:800]
            append_history(summary, str(self.file_path))
            
            try:
                crash_id = self.database_manager.add_crash_record(
                    file_path=str(self.file_path),
                    summary=summary,
                    loader=self.loader_type or "Unknown",
                    mod_count=len(self.mods),
                    file_hash=self.file_checksum
                )
                if crash_id > 0 and self.cause_counts:
                    causes_list = [
                        {"type": cause, "desc": f"Occurred {count} times", "confidence": 1.0} 
                        for cause, count in self.cause_counts.items()
                    ]
                    self.database_manager.add_crash_causes(crash_id, causes_list)
                if self.mods:
                    mods_list = [
                        {"id": mod_id, "version": v} 
                        for mod_id, versions in self.mods.items() 
                        for v in versions
                    ]
                    self.database_manager.update_mod_index(mods_list, self.loader_type or "Unknown")
            except Exception as e:
                logger.error(f"[Dual-Write Warning] DatabaseManager failed: {e}")
        except Exception:
            pass

    def display_results(self: AnalysisMixinHost) -> None:
        """
        批量显示分析结果。
        
        使用分批插入避免 UI 阻塞。
        """
        if not self.analysis_results:
            self.result_text.config(state="disabled")
            return
        
        self.result_text.config(state="normal")
        self.result_text.delete("1.0", tk.END)
        
        batch_size = 50
        results = self.analysis_results.copy()
        
        def insert_batch(start_idx: int) -> None:
            end_idx = min(start_idx + batch_size, len(results))
            for i in range(start_idx, end_idx):
                line = results[i]
                if "智能" in line and "建议" in line:
                    self.result_text.insert(tk.END, line + "\n", "ai_header")
                elif "AI 深度理解" in line or "关键特征匹配" in line:
                    self.result_text.insert(tk.END, line + "\n", "ai_content")
                else:
                    self.result_text.insert(tk.END, line + "\n")
            
            if end_idx < len(results):
                self.root.after(10, lambda: insert_batch(end_idx))
            else:
                self.result_text.see(tk.END)
                self.result_text.config(state="disabled")
        
        insert_batch(0)
