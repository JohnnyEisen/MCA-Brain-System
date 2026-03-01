from __future__ import annotations
import logging
from typing import Iterable, List, Optional

from .base import Detector
from .contracts import AnalysisContext, DetectionResult

logger = logging.getLogger(__name__)


class DetectorRegistry:
    """检测器注册表（策略模式）。"""
    
    # 静态缓存，避免重复扫描磁盘 (IO Storm Fix)
    _builtin_class_cache = set()
    _inited = False

    def __init__(self, detectors: Optional[Iterable[Detector]] = None) -> None:
        self._detectors: List[Detector] = list(detectors or [])

    def register(self, detector: Detector) -> Detector:
        self._detectors.append(detector)
        return detector

    def list(self) -> List[Detector]:
        return list(self._detectors)

    def load_builtins(self):
        """Auto-discover and register all built-in detectors."""
        # 1. Hit Cache (Fast Path)
        if DetectorRegistry._inited and DetectorRegistry._builtin_class_cache:
            for cls in DetectorRegistry._builtin_class_cache:
                try:
                    self.register(cls())
                except Exception:
                    pass
            return

        # 2. Slow Path (Discovery)
        import importlib
        import pkgutil
        import inspect
        import mca_core.detectors
        from mca_core.detectors.base import Detector

        package = mca_core.detectors
        prefix = package.__name__ + "."

        detected_classes = set()

        # Dynamic Scan
        try:
            for _, name, _ in pkgutil.iter_modules(package.__path__, prefix):
                if name.endswith(".registry") or name.endswith(".base") or name.endswith(".contracts"):
                    continue
                
                try:
                    module = importlib.import_module(name)
                    for member_name, member in inspect.getmembers(module):
                        if inspect.isclass(member) and issubclass(member, Detector) and member is not Detector:
                            detected_classes.add(member)
                except Exception as e:
                    logger.error(f"Failed to load detector module {name}: {e}")
        except Exception as e:
            logger.warning(f"Dynamic discovery failed ({e}), switching to fallback.")

        # 3. Static Fallback (Frozen Environment / IO Error Safety)
        if not detected_classes:
            logger.info("No detectors found dynamically. Using static fallback.")
            self._load_static_fallback(detected_classes)

        # 4. Update Cache & Instantiate
        DetectorRegistry._builtin_class_cache = detected_classes
        DetectorRegistry._inited = True
        
        for cls in detected_classes:
            try:
                self.register(cls())
            except Exception as e:
                logger.error(f"Failed to instantiate detector {cls.__name__}: {e}")

    def _load_static_fallback(self, classes_set):
        """Hardcoded imports when dynamic scanning fails (e.g. inside PyInstaller EXE)."""
        try:
            from .loader import LoaderDetector
            from .out_of_memory import OutOfMemoryDetector
            from .jvm_issues import JvmIssuesDetector
            from .version_conflicts import VersionConflictsDetector
            from .duplicate_mods import DuplicateModsDetector
            from .mod_conflicts import ModConflictsDetector
            from .shader_world_conflicts import ShaderWorldConflictsDetector
            from .missing_dependencies import MissingDependenciesDetector
            from .missing_geckolib import MissingGeckoLibDetector
            from .geckolib_more import GeckoLibMoreDetector
            from .gl_errors import GlErrorsDetector
            
            classes_set.add(LoaderDetector)
            classes_set.add(OutOfMemoryDetector)
            classes_set.add(JvmIssuesDetector)
            classes_set.add(VersionConflictsDetector)
            classes_set.add(DuplicateModsDetector)
            classes_set.add(ModConflictsDetector)
            classes_set.add(ShaderWorldConflictsDetector)
            classes_set.add(MissingDependenciesDetector)
            classes_set.add(MissingGeckoLibDetector)
            classes_set.add(GeckoLibMoreDetector)
            classes_set.add(GlErrorsDetector)
        except ImportError as e:
             logger.critical(f"Static fallback failed: {e}")

    def run_all(self, analyzer) -> List[DetectionResult]:
        crash_log = getattr(analyzer, "crash_log", "") or ""
        context = AnalysisContext(analyzer=analyzer, crash_log=crash_log)
        event_bus = getattr(analyzer, "event_bus", None)
        for detector in self._detectors:
            try:
                detector.detect(crash_log, context)
                if event_bus:
                    try:
                        from mca_core.events import AnalysisEvent, EventTypes
                        event_bus.publish(AnalysisEvent(EventTypes.DETECTOR_COMPLETE, {"detector": detector.get_name()}))
                    except Exception:
                        pass
            except Exception as exc:
                logger.exception("Detector failed (%s): %s", detector.get_name(), exc)
                # 保持行为稳定：不要在这里修改 analysis_results
        return context.results

    def run_all_parallel(self, analyzer, max_workers: int = 4, executor=None) -> List[DetectionResult]:
        """使用 ThreadPoolExecutor 并行运行检测器。
        
        Args:
            analyzer: 分析器实例
            max_workers: 最大工作线程数 (当 executor 为 None 时生效)
            executor: 可选的自定义 Executor (例如来自 BrainCore)
        """
        from concurrent.futures import ThreadPoolExecutor, wait
        
        crash_log = getattr(analyzer, "crash_log", "") or ""
        # 共享上下文（线程安全由 AnalysisContext 通过 analyzer.lock 处理）
        context = AnalysisContext(analyzer=analyzer, crash_log=crash_log)
        event_bus = getattr(analyzer, "event_bus", None)

        def _run_one(detector):
            try:
                detector.detect(crash_log, context)
                if event_bus:
                    try:
                        from mca_core.events import AnalysisEvent, EventTypes
                        event_bus.publish(AnalysisEvent(EventTypes.DETECTOR_COMPLETE, {"detector": detector.get_name()}))
                    except Exception:
                        pass
            except Exception as exc:
                logger.exception("Detector failed (%s): %s", detector.get_name(), exc)
                try:
                    if hasattr(analyzer, "_auto_test_write_log"):
                        analyzer._auto_test_write_log(f"Detector Error {detector.get_name()}: {exc}")
                except:
                    pass

        if executor:
            # 使用外部提供的 Executor (例如 BrainCore 的资源池)
            futures = [executor.submit(_run_one, d) for d in self._detectors]
            wait(futures)
        else:
            # 内部创建临时的 ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=max_workers) as internal_executor:
                futures = [internal_executor.submit(_run_one, d) for d in self._detectors]
                wait(futures)
            
        return context.results
