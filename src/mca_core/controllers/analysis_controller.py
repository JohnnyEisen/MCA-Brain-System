"""Analysis Controller Module.

Coordinates analysis flow, state management, and result processing.
Extracted from app.py for business logic and UI decoupling.
"""

import os
import threading
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable, List, Dict, Set, Any, Tuple
from collections import Counter, defaultdict, OrderedDict

from mca_core.errors import TaskCancelledError
from mca_core.regex_cache import RegexCache
from mca_core.history_manager import append_history


logger = logging.getLogger(__name__)


@dataclass
class AnalysisState:
    """分析状态数据容器。"""
    analysis_results: List[str] = field(default_factory=list)
    mods: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    mod_names: Dict[str, str] = field(default_factory=dict)
    dependency_pairs: Set[Tuple[str, str]] = field(default_factory=set)
    loader_type: Optional[str] = None
    cause_counts: Counter = field(default_factory=Counter)
    file_checksum: Optional[str] = None
    crash_log: str = ""
    file_path: str = ""


class AnalysisController:
    """
    分析流程控制器。
    
    负责协调崩溃日志分析的完整流程：
    1. 加载器检测
    2. Mod 信息提取
    3. 检测器执行
    4. 智能诊断
    5. 结果汇总与记录
    """
    
    def __init__(
        self,
        state: AnalysisState,
        detector_registry: Any,
        diagnostic_engine: Any = None,
        crash_pattern_learner: Any = None,
        plugin_registry: Any = None,
        brain: Any = None,
        database_manager: Any = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        ui_schedule_callback: Optional[Callable[[Callable], None]] = None,
        is_cancelled_callback: Optional[Callable[[], bool]] = None,
    ):
        """
        初始化分析控制器。
        
        Args:
            state: 分析状态容器
            detector_registry: 检测器注册表
            diagnostic_engine: 诊断引擎（可选）
            crash_pattern_learner: 模式学习器（可选）
            plugin_registry: 插件注册表（可选）
            brain: Brain 系统实例（可选）
            database_manager: 数据库管理器（可选）
            progress_callback: 进度回调
            ui_schedule_callback: UI 调度回调
            is_cancelled_callback: 取消检查回调
        """
        self.state = state
        self.detector_registry = detector_registry
        self.diagnostic_engine = diagnostic_engine
        self.crash_pattern_learner = crash_pattern_learner
        self.plugin_registry = plugin_registry
        self.brain = brain
        self.database_manager = database_manager
        
        self._progress = progress_callback
        self._schedule_ui = ui_schedule_callback
        self._is_cancelled = is_cancelled_callback or (lambda: False)
        
        # 缓存与锁
        self._analysis_cache: OrderedDict[str, Dict] = OrderedDict()
        self._cache_lock = threading.RLock()
        self._cache_max_size = 100
    
    def run_analysis(self, analyzer_context: Any = None) -> bool:
        """
        执行完整分析流程。
        
        Args:
            analyzer_context: 分析器上下文（用于检测器）
            
        Returns:
            是否成功完成
        """
        try:
            # 清理状态
            self.state.analysis_results.clear()
            self.state.cause_counts.clear()
            
            # 执行核心逻辑
            self._run_analysis_logic(analyzer_context)
            
            # 记录历史
            self._record_history()
            
            return True
            
        except TaskCancelledError:
            self.state.analysis_results.append(">> 分析操作已由用户取消。")
            self._report_progress(0, "已取消")
            return False
            
        except Exception as e:
            logger.exception("分析过程发生不可预期的错误")
            self.state.analysis_results.append(f"分析出错: {e}")
            self._report_progress(0, "分析出错")
            return False
    
    def _run_analysis_logic(self, analyzer_context: Any = None):
        """主分析流程逻辑。"""
        # 1) 预备检查
        if self._is_cancelled():
            raise TaskCancelledError()
        
        # 2) 检测加载器
        self.state.loader_type = self._detect_loader()
        self._report_progress(1/6, "检测加载器")
        
        # 3) 提取 Mod
        if self._is_cancelled():
            raise TaskCancelledError()
        self._extract_mods()
        self._report_progress(2/6, "提取 Mod 信息")
        
        # 4) 并行运行检测器
        if self._is_cancelled():
            raise TaskCancelledError()
        self._run_detectors(analyzer_context)
        self._report_progress(3/6, "执行检测器")
        
        # 5) 智能诊断与依赖分析
        if self._is_cancelled():
            raise TaskCancelledError()
        if self.diagnostic_engine:
            self._run_smart_diagnostics()
            self._run_dependency_analysis()
        
        self._report_progress(4/6, "智能诊断")
        
        # 6) 生成摘要
        self._build_precise_summary()
        self._report_progress(5/6, "生成摘要")
        
        # 7) 数据规整与去重
        self.state.analysis_results = list(dict.fromkeys(self.state.analysis_results))
        self._clean_dependency_pairs()
        
        # 8) 自动学习
        if self.crash_pattern_learner:
            try:
                self.crash_pattern_learner.learn_from_crash(
                    self.state.crash_log, 
                    self.state.analysis_results
                )
            except Exception as e:
                logger.warning(f"智能学习记录失败: {e}")
        
        # 9) 插件回调
        if self.plugin_registry:
            disabled_plugins = getattr(analyzer_context, "_disabled_plugins", set())
            for plugin in self.plugin_registry.list():
                plugin_key = f"{getattr(plugin, '__module__', 'unknown')}:{getattr(plugin, '__name__', 'plugin_entry')}"
                if plugin_key in disabled_plugins:
                    continue
                try:
                    plugin(analyzer_context)
                except Exception as e:
                    logger.warning(f"插件执行异常: {e}")
    
    def _detect_loader(self) -> str:
        """检测加载器类型。"""
        txt = (self.state.crash_log or "").lower()
        if "neoforge" in txt:
            return "NeoForge"
        if "forge" in txt and "fml" in txt:
            return "Forge"
        if "fabric loader" in txt or ("fabric" in txt and "quilt" not in txt):
            return "Fabric"
        if "quilt" in txt:
            return "Quilt"
        return "Unknown"
    
    def _extract_mods(self):
        """提取 Mod 信息。"""
        text = self.state.crash_log or ""
        pattern = r"(?:^|[\/\\])([a-zA-Z0-9_\-]+)-(\d[\w\.\-]+)\.jar"
        
        seen = set()
        for m in RegexCache.finditer(pattern, text):
            raw_id, ver = m.groups()
            modid = self._clean_modid(raw_id)
            if modid and modid not in seen:
                self.state.mods[modid].add(ver)
                seen.add(f"{modid}:{ver}")
        
        self.state.analysis_results.append(f"扫描完成：发现 {len(self.state.mods)} 个模组文件。")
    
    def _clean_modid(self, raw: str) -> Optional[str]:
        """清理和规范化 Mod ID。"""
        if not raw:
            return None
        # 简单清理
        modid = raw.strip().lower()
        # 过滤无效名称
        invalid = {"mod", "jar", "file", "unknown"}
        if modid in invalid or len(modid) < 2:
            return None
        return modid
    
    def _run_detectors(self, analyzer_context: Any = None):
        """运行所有检测器。"""
        self._extract_dependency_pairs()
        
        executor = None
        if self.brain:
            executor = self.brain.thread_pool
            logger.info("使用 Brain System 算力加速检测器执行")
        
        workers = min(os.cpu_count() or 4, 8)
        
        if self.detector_registry and analyzer_context:
            self.detector_registry.run_all_parallel(
                analyzer_context, 
                max_workers=workers, 
                executor=executor
            )
    
    def _extract_dependency_pairs(self):
        """提取依赖关系。"""
        text = self.state.crash_log or ""
        
        # 模式1: Missing mod 'X' needed by 'Y'
        p1 = r"Missing mod '([^']+)' needed by '([^']+)'"
        for m in RegexCache.finditer(p1, text):
            self.state.dependency_pairs.add((m.group(2), m.group(1)))
            self.state.analysis_results.append(
                f"发现依赖关系: {m.group(2)} -> {m.group(1)} (缺失)"
            )
        
        # 模式2: Mod X requires Y
        p2 = r"Mod ([^ ]+) requires ([^ \n]+)"
        for m in RegexCache.finditer(p2, text):
            self.state.dependency_pairs.add((m.group(1), m.group(2)))
    
    def _clean_dependency_pairs(self):
        """清理依赖对。"""
        if not self.state.dependency_pairs:
            return
        self.state.dependency_pairs = {
            (p, c) for p, c in self.state.dependency_pairs 
            if p and c and p != c
        }
    
    def _run_smart_diagnostics(self):
        """执行智能诊断。"""
        if self.diagnostic_engine:
            res = self.diagnostic_engine.analyze(self.state.crash_log)
            if res:
                self.state.analysis_results.append(">> 智能诊断建议:")
                self.state.analysis_results.extend([f" - {r}" for r in res])
    
    def _run_dependency_analysis(self):
        """依赖分析（占位符）。"""
        pass
    
    def _build_precise_summary(self):
        """构建分析摘要。"""
        summary = [
            f"加载器: {self.state.loader_type.upper() if self.state.loader_type else '未知'}",
            f"Mod总数: {len(self.state.mods)}"
        ]
        self.state.analysis_results[0:0] = summary
    
    def _record_history(self):
        """Record analysis history."""
        try:
            summary = "; ".join(self.state.analysis_results[:6])[:800]
            
            # Use history_manager for rotation and writing
            append_history(summary, self.state.file_path)
            
            # Write to database
            self._write_to_database(summary)
            
        except Exception as e:
            logger.warning(f"Failed to record history: {e}")
    
    def _write_to_database(self, summary: str) -> None:
        """写入数据库（使用原子写入 API）。"""
        if not self.database_manager:
            return
        
        try:
            causes_list = [
                {"type": cause, "desc": f"Occurred {count} times", "confidence": 1.0}
                for cause, count in self.state.cause_counts.items()
            ]
            
            # 构建 Mod 列表
            mods_list = [
                {"id": mod_id, "version": v}
                for mod_id, versions in self.state.mods.items()
                for v in versions
            ]
            
            # 使用原子写入 API（单事务完成所有操作）
            self.database_manager.write_analysis_result(
                file_path=str(self.state.file_path),
                summary=summary,
                loader=self.state.loader_type or "Unknown",
                mod_count=len(self.state.mods),
                file_hash=self.state.file_checksum,
                causes=causes_list,
                mods=mods_list,
            )
                
        except Exception as e:
            logger.error(f"数据库写入失败: {e}")
    
    def _report_progress(self, value: float, message: str):
        """报告进度。"""
        if self._progress is None:
            return
        progress_cb = self._progress
        if self._schedule_ui is not None:
            self._schedule_ui(lambda: progress_cb(value, message))
        else:
            progress_cb(value, message)
    
    def get_cached_result(self, checksum: str) -> Optional[Dict]:
        """获取缓存的分析结果（线程安全）。"""
        with self._cache_lock:
            value = self._analysis_cache.get(checksum)
            if value is not None:
                self._analysis_cache.move_to_end(checksum)
            return value
    
    def cache_result(self, checksum: str) -> None:
        """缓存当前分析结果（线程安全）。"""
        if checksum:
            with self._cache_lock:
                if checksum in self._analysis_cache:
                    self._analysis_cache.move_to_end(checksum)
                while len(self._analysis_cache) >= self._cache_max_size:
                    self._analysis_cache.popitem(last=False)
                mods_light = {k: list(v) for k, v in self.state.mods.items()} if self.state.mods else {}
                self._analysis_cache[checksum] = {
                    'results': list(self.state.analysis_results),
                    'mods': mods_light,
                    'dep_pairs': frozenset(self.state.dependency_pairs),
                    'loader': self.state.loader_type,
                    'causes': dict(self.state.cause_counts)
                }
