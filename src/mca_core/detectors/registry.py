"""
检测器注册表模块

实现检测器注册和执行的策略模式，支持优先级排序和并行执行。

类说明:
    - DetectorRegistry: 检测器注册表，管理检测器的注册、发现和执行
"""

from __future__ import annotations

import importlib
import inspect
import logging
from concurrent.futures import Executor, ThreadPoolExecutor, wait
from typing import TYPE_CHECKING, Any, Callable, Iterable, List, Optional, Set, Type

from .base import Detector
from .contracts import AnalysisContext, DetectionResult

if TYPE_CHECKING:
    from mca_core.events import EventBus

logger = logging.getLogger(__name__)


class DetectorRegistry:
    """
    检测器注册表（策略模式 + 单例模式）。
    
    支持检测器的注册、自动发现、优先级排序和执行。
    提供串行和并行两种执行模式。
    
    单例模式确保全局只有一个注册表实例，避免重复初始化检测器。
    
    类属性:
        _instance: 单例实例
        _builtin_class_cache: 内置检测器类缓存，避免重复扫描磁盘
        _inited: 是否已初始化缓存
    
    Attributes:
        _detectors: 已注册的检测器列表
        _sorted: 是否已按优先级排序
    
    方法:
        - get_instance: 获取单例实例（推荐）
        - register: 注册检测器
        - list: 获取按优先级排序的检测器列表
        - load_builtins: 自动发现并注册内置检测器
        - run_all: 串行执行所有检测器
        - run_all_parallel: 并行执行所有检测器
        - reset: 重置单例（仅用于测试）
    """

    _instance: Optional["DetectorRegistry"] = None
    _builtin_class_cache: Set[Type[Detector]] = set()
    _inited: bool = False

    def __new__(cls, detectors: Optional[Iterable[Detector]] = None) -> "DetectorRegistry":
        """
        创建或返回单例实例。
        
        Args:
            detectors: 初始检测器集合（仅在首次创建时生效）
            
        Returns:
            DetectorRegistry 单例实例
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._detectors = list(detectors or [])
            cls._instance._sorted = False
            cls._instance._initialized = False
        return cls._instance

    @classmethod
    def get_instance(cls) -> "DetectorRegistry":
        """
        获取单例实例。
        
        如果实例不存在则创建并自动加载内置检测器。
        
        Returns:
            DetectorRegistry 单例实例
        """
        if cls._instance is None:
            instance = cls()
            instance.load_builtins()
        assert cls._instance is not None
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """
        重置单例实例。
        
        仅用于测试场景，生产代码不应调用。
        """
        cls._instance = None
        cls._builtin_class_cache.clear()
        cls._inited = False

    def __init__(self, detectors: Optional[Iterable[Detector]] = None) -> None:
        """
        初始化检测器注册表。
        
        注意：单例模式下，后续调用不会重新初始化。
        
        Args:
            detectors: 初始检测器集合
        """
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._detectors: List[Detector] = list(detectors or [])
        self._sorted: bool = False
        self._initialized: bool = True

    def register(self, detector: Detector) -> Detector:
        """
        注册检测器。
        
        Args:
            detector: 要注册的检测器实例
            
        Returns:
            注册的检测器实例
        """
        self._detectors.append(detector)
        self._sorted = False
        return detector

    def list(self) -> List[Detector]:
        """
        获取按优先级排序的检测器列表。
        
        Returns:
            排序后的检测器列表（优先级低的在前）
        """
        if not self._sorted:
            self._detectors.sort(key=lambda d: d.get_priority())
            self._sorted = True
        return list(self._detectors)

    def load_builtins(self) -> None:
        """自动发现并注册所有内置检测器。"""
        if DetectorRegistry._inited and DetectorRegistry._builtin_class_cache:
            self._load_from_cache()
            return

        detected_classes: Set[Type[Detector]] = set()
        self._dynamic_discovery(detected_classes)

        if not detected_classes:
            logger.info("No detectors found dynamically. Using static fallback.")
            self._load_static_fallback(detected_classes)

        DetectorRegistry._builtin_class_cache = detected_classes
        DetectorRegistry._inited = True

        for cls in detected_classes:
            try:
                self.register(cls())
            except Exception as e:
                logger.error(f"Failed to instantiate detector {cls.__name__}: {e}")

    def _load_from_cache(self) -> None:
        """从缓存加载检测器。"""
        for cls in DetectorRegistry._builtin_class_cache:
            try:
                self.register(cls())
            except Exception:
                pass

    def _dynamic_discovery(self, classes_set: Set[Type[Detector]]) -> None:
        """
        动态发现检测器类。
        
        Args:
            classes_set: 用于存储发现的检测器类的集合
        """
        import pkgutil

        try:
            import mca_core.detectors
        except ImportError:
            return

        package = mca_core.detectors
        prefix = package.__name__ + "."

        try:
            for _, name, _ in pkgutil.iter_modules(package.__path__, prefix):
                if name.endswith(".registry") or name.endswith(".base") or name.endswith(".contracts"):
                    continue

                try:
                    module = importlib.import_module(name)
                    for _, member in inspect.getmembers(module):
                        if (
                            inspect.isclass(member)
                            and issubclass(member, Detector)
                            and member is not Detector
                        ):
                            classes_set.add(member)
                except Exception as e:
                    logger.error(f"Failed to load detector module {name}: {e}")
        except Exception as e:
            logger.warning(f"Dynamic discovery failed ({e}), switching to fallback.")

    def _load_static_fallback(self, classes_set: Set[Type[Detector]]) -> None:
        """
        静态回退：当动态扫描失败时使用硬编码导入。
        
        Args:
            classes_set: 用于存储检测器类的集合
        """
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

            classes_set.update([
                LoaderDetector,
                OutOfMemoryDetector,
                JvmIssuesDetector,
                VersionConflictsDetector,
                DuplicateModsDetector,
                ModConflictsDetector,
                ShaderWorldConflictsDetector,
                MissingDependenciesDetector,
                MissingGeckoLibDetector,
                GeckoLibMoreDetector,
                GlErrorsDetector,
            ])
        except ImportError as e:
            logger.critical(f"Static fallback failed: {e}")

    def run_all(self, analyzer: Any) -> List[DetectionResult]:
        """
        串行执行所有检测器。
        
        Args:
            analyzer: 分析器实例
            
        Returns:
            检测结果列表
        """
        crash_log = getattr(analyzer, "crash_log", "") or ""
        context = AnalysisContext(analyzer=analyzer, crash_log=crash_log)
        emit_fn = self._create_event_emitter(analyzer)

        for detector in self._detectors:
            try:
                detector.detect(crash_log, context)
                if emit_fn:
                    try:
                        emit_fn(detector.get_name())
                    except Exception:
                        pass
            except Exception as exc:
                logger.exception("Detector failed (%s): %s", detector.get_name(), exc)

        return context.results

    def run_all_parallel(
        self,
        analyzer: Any,
        max_workers: int = 4,
        executor: Optional[Executor] = None
    ) -> List[DetectionResult]:
        """
        并行执行所有检测器。
        
        Args:
            analyzer: 分析器实例
            max_workers: 最大工作线程数（当 executor 为 None 时生效）
            executor: 可选的自定义 Executor（例如来自 BrainCore）
            
        Returns:
            检测结果列表
        """
        crash_log = getattr(analyzer, "crash_log", "") or ""
        context = AnalysisContext(analyzer=analyzer, crash_log=crash_log)
        emit_fn = self._create_event_emitter(analyzer)

        def _run_one(detector: Detector) -> None:
            try:
                detector.detect(crash_log, context)
                if emit_fn:
                    try:
                        emit_fn(detector.get_name())
                    except Exception:
                        pass
            except Exception as exc:
                logger.exception("Detector failed (%s): %s", detector.get_name(), exc)
                try:
                    if hasattr(analyzer, "_auto_test_write_log"):
                        analyzer._auto_test_write_log(
                            f"Detector Error {detector.get_name()}: {exc}"
                        )
                except Exception:
                    pass

        if executor:
            futures = [executor.submit(_run_one, d) for d in self._detectors]
            wait(futures)
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as internal_executor:
                futures = [internal_executor.submit(_run_one, d) for d in self._detectors]
                wait(futures)

        return context.results

    def _create_event_emitter(self, analyzer: Any) -> Optional[Callable[[str], None]]:
        """
        创建事件发射函数。
        
        Args:
            analyzer: 分析器实例
            
        Returns:
            事件发射函数，如果无法创建则返回 None
        """
        event_bus: Optional[EventBus] = getattr(analyzer, "event_bus", None)
        if not event_bus:
            return None

        try:
            from mca_core.events import AnalysisEvent, EventTypes

            def emit_detector_complete(detector_name: str) -> None:
                event_bus.publish(
                    AnalysisEvent(
                        EventTypes.DETECTOR_COMPLETE,
                        {"detector": detector_name},
                    )
                )

            return emit_detector_complete
        except Exception:
            return None
