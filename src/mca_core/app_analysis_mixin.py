"""Analysis Mixin - Core Analysis Logic"""

from __future__ import annotations
import os
import sys
import copy
import csv
import threading
import logging
from collections import defaultdict, Counter, OrderedDict
from datetime import datetime
from typing import TYPE_CHECKING, Protocol, runtime_checkable, Any
import tkinter as tk
from tkinter import messagebox
import tkinter.ttk as ttk

if TYPE_CHECKING:
    from mca_core.plugins import PluginRegistry
    from mca_core.detectors import DetectorRegistry
    from mca_core.services.database import DatabaseManager
    from config.app_config import AppConfig
    pass

from mca_core.regex_cache import RegexCache
from mca_core.errors import TaskCancelledError
from mca_core.threading_utils import submit_task
from mca_core.history_manager import append_history
from config.constants import HISTORY_FILE, BASE_DIR

logger = logging.getLogger(__name__)


@runtime_checkable
class AnalysisMixinHost(Protocol):
    """Protocol defining the interface required by AnalysisMixin."""
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
    plugin_registry: PluginRegistry
    detector_registry: DetectorRegistry
    database_manager: DatabaseManager
    crash_pattern_learner: Any
    brain: Any
    HAS_NEW_MODULES: bool
    progress: ttk.Progressbar
    result_text: tk.Text
    app_config: AppConfig | None
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


class AnalysisMixin:
    """Mixin for core analysis logic."""
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
    
    def start_analysis(self: AnalysisMixinHost):
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

    def _report_progress(self: AnalysisMixinHost, val: float, msg: str = ""):
        if getattr(self, "_is_auto_testing", False):
            return
        self.root.after(0, lambda: self.status_var.set(msg))
        if hasattr(self, 'progress_reporter'):
            self.progress_reporter.report(val, msg)

    def _run_analysis_logic(self: AnalysisMixinHost):
        """Core analysis logic with caching"""
        logger.info("[ANALYSIS] _run_analysis_logic started")
        self._cache_hit = False
        
        # 1. Check cache
        if self.file_checksum:
            with self.lock:
                cached = self._analysis_cache.get(self.file_checksum)
            if cached:
                logger.info("[ANALYSIS] Cache hit, skipping analysis")
                self.analysis_results[:] = cached['results']
                self.mods = cached['mods']
                self.dependency_pairs = cached['dep_pairs']
                self.loader_type = cached['loader']
                self.cause_counts.clear()
                self.cause_counts.update(cached['causes'])
                self._cache_hit = True
                self._report_progress(1.0, "分析完成 (缓存命中)")
                return
        
        logger.info("[ANALYSIS] Cache miss, starting full analysis")
        
        # 2. Run analysis
        if self._is_cancelled(): raise TaskCancelledError
        logger.debug("[ANALYSIS] Detecting loader")
        self.loader_type = self._detect_loader()
        self._report_progress(1/6, "检测加载器")
        if self._is_cancelled(): raise TaskCancelledError
        logger.debug("[ANALYSIS] Extracting mods")
        self._extract_mods()
        self._report_progress(2/6, "提取 Mod 信息")
        if self._is_cancelled(): raise TaskCancelledError
        logger.info("[ANALYSIS] Running detectors")
        self._run_detectors()
        logger.info("[ANALYSIS] Detectors complete")
        self._report_progress(3/6, "执行检测器")
        if self._is_cancelled(): raise TaskCancelledError
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
        for plugin in self.plugin_registry.list():
            try: 
                plugin(self)
            except Exception as e: 
                logger.warning(f"插件 {plugin} 执行异常: {e}")
        
        # 3. Write cache (LRU eviction, locked)
        # V-014 Fix: Use OrderedDict for proper LRU behavior
        if self.file_checksum:
            with self.lock:
                max_size = getattr(self, '_cache_max_size', 100)
                
                # Ensure _analysis_cache is OrderedDict for proper LRU
                if not hasattr(self, '_analysis_cache_ordered'):
                    from collections import OrderedDict
                    self._analysis_cache = OrderedDict(self._analysis_cache)
                    self._analysis_cache_ordered = True
                
                # If key exists, move to end (most recently used)
                if self.file_checksum in self._analysis_cache:
                    self._analysis_cache.move_to_end(self.file_checksum)
                else:
                    # Evict oldest entries if at capacity
                    while len(self._analysis_cache) >= max_size:
                        self._analysis_cache.popitem(last=False)  # FIFO eviction
                    
                    self._analysis_cache[self.file_checksum] = {
                        'results': list(self.analysis_results),
                        'mods': copy.deepcopy(self.mods),
                        'dep_pairs': set(self.dependency_pairs),
                        'loader': self.loader_type,
                        'causes': self.cause_counts.copy()
                    }

    def add_cause(self: AnalysisMixinHost, cause_label: str):
        with self.lock:
            self.cause_counts[cause_label] += 1

    def _extract_mods(self: AnalysisMixinHost):
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

    def _run_detectors(self: AnalysisMixinHost):
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

    def _run_analysis_thread(self: AnalysisMixinHost):
        """Background thread entry, handles caching and UI updates"""
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
    def _post_analysis_ui_update(self: AnalysisMixinHost, cached: bool):
        self.root.after(0, self.display_results)
        delay = 100 if cached else 300
        self.root.after(delay, self.update_dependency_graph)
        # Use background thread for pie chart to avoid UI blocking
        self.root.after(delay, lambda: submit_task(self.update_cause_chart))

    def _detect_loader(self: AnalysisMixinHost) -> str:
        txt = (self.crash_log or "").lower()
        if "neoforge" in txt: return "NeoForge"
        if "forge" in txt and "fml" in txt: return "Forge"
        if "fabric loader" in txt or ("fabric" in txt and "quilt" not in txt): return "Fabric"
        if "quilt" in txt: return "Quilt"
        return "Unknown"

    def _clean_dependency_pairs(self: AnalysisMixinHost):
        if not self.dependency_pairs: return
        self.dependency_pairs = {(p, c) for p, c in self.dependency_pairs if p and c and p != c}

    def _extract_dependency_pairs(self: AnalysisMixinHost):
        text = self.crash_log or ""
        p1 = r"Missing mod '([^']+)' needed by '([^']+)'"
        for m in RegexCache.finditer(p1, text):
            self.dependency_pairs.add((m.group(2), m.group(1)))
            self.analysis_results.append(f"发现依赖关系: {m.group(2)} -> {m.group(1)} (缺失)")
        p2 = r"Mod ([^ ]+) requires ([^ \n]+)"
        for m in RegexCache.finditer(p2, text):
            self.dependency_pairs.add((m.group(1), m.group(2)))

    def _run_smart_diagnostics(self: AnalysisMixinHost):
        if self.diagnostic_engine and self.HAS_NEW_MODULES:
            res = self.diagnostic_engine.analyze(self.crash_log)
            if res:
                self.analysis_results.append(">> 智能诊断建议:")
                self.analysis_results.extend([f" - {r}" for r in res])

    def _run_learning_based_analysis(self: AnalysisMixinHost):
        if not self.crash_pattern_learner: return
        self._start_ai_init_if_needed()
        try:
            suggestions = self.crash_pattern_learner.suggest_solutions(self.crash_log)
            if suggestions:
                self.analysis_results.append(">> 智能学习引擎建议:")
                for s in suggestions:
                    self.analysis_results.append(f" - {s.text}")
        except Exception as e:
            logger.warning(f"智能学习分析执行出错: {e}")

    def _run_dependency_analysis(self: AnalysisMixinHost):
        pass

    def _build_precise_summary(self: AnalysisMixinHost):
        summary = [
            f"加载器: {self.loader_type.upper() if self.loader_type else '未知'}",
            f"Mod总数: {len(self.mods)}"
        ]
        self.analysis_results[0:0] = summary

    def _record_history(self: AnalysisMixinHost):
        """Use unified history_manager to record history"""
        try:
            summary = "; ".join(self.analysis_results[:6])[:800]
            
            # Use history_manager for unified processing
            append_history(summary, str(self.file_path))
            
            # Database record
            try:
                crash_id = self.database_manager.add_crash_record(
                    file_path=str(self.file_path),
                    summary=summary,
                    loader=self.loader_type or "Unknown",
                    mod_count=len(self.mods),
                    file_hash=self.file_checksum
                )
                if crash_id > 0 and self.cause_counts:
                    causes_list = [{"type": cause, "desc": f"Occurred {count} times", "confidence": 1.0} for cause, count in self.cause_counts.items()]
                    self.database_manager.add_crash_causes(crash_id, causes_list)
                if self.mods:
                    mods_list = [{"id": mod_id, "version": v} for mod_id, versions in self.mods.items() for v in versions]
                    self.database_manager.update_mod_index(mods_list, self.loader_type or "Unknown")
            except Exception as e:
                logger.error(f"[Dual-Write Warning] DatabaseManager failed: {e}")
        except Exception:
            pass

    def display_results(self: AnalysisMixinHost):
        """Batch insert results to avoid UI blocking"""
        if not self.analysis_results:
            self.result_text.config(state="disabled")
            return
        
        self.result_text.config(state="normal")
        self.result_text.delete("1.0", tk.END)
        
        # Batch insert, 50 lines per batch
        batch_size = 50
        results = self.analysis_results.copy()
        
        def insert_batch(start_idx):
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
                # More to insert, schedule next batch
                self.root.after(10, lambda: insert_batch(end_idx))
            else:
                # All done
                self.result_text.see(tk.END)
                self.result_text.config(state="disabled")
        
        insert_batch(0)
