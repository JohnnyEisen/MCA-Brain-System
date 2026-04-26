"""
应用控制器模块

提供基于组合模式的控制器架构，作为 Mixin 模式的替代方案。

模块说明:
    本模块实现了控制器模式，将应用功能拆分为独立的控制器类。
    相比 Mixin 模式，控制器模式具有以下优势：
        - 职责更清晰
        - 更易于测试
        - 避免多重继承复杂性
        - 支持依赖注入
    
    主要组件:
        - ControllerBase: 控制器基类
        - AnalysisController: 分析控制器
        - FileController: 文件操作控制器
        - UIController: UI 控制器
        - AutoTestController: 自动测试控制器

使用方式:
    方式一：直接使用控制器
        >>> analysis = AnalysisController(detector_registry, event_bus)
        >>> results = analysis.analyze(crash_log)
    
    方式二：通过 DI 容器注入
        >>> container = DIContainer()
        >>> container.register_singleton(DetectorRegistry)
        >>> container.register_singleton(AnalysisController)
        >>> analysis = container.resolve(AnalysisController)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Protocol

if TYPE_CHECKING:
    from mca_core.detectors import DetectorRegistry
    from mca_core.detectors.contracts import DetectionResult
    from mca_core.events import EventBus
    from mca_core.services.database import DatabaseManager
    from mca_core.services.log_service import LogService
    from config.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class AppContext(Protocol):
    """
    应用上下文协议。
    
    定义控制器需要访问的应用级资源。
    """
    
    event_bus: "EventBus"
    config: "ConfigManager"
    database: "DatabaseManager"
    log_service: "LogService"
    
    def get_resource(self, key: str) -> Any:
        """获取资源。"""
        ...


class ControllerBase(ABC):
    """
    控制器基类。
    
    所有控制器的抽象基类，提供通用功能。
    
    Attributes:
        _context: 应用上下文
        _event_bus: 事件总线
    
    方法:
        - initialize: 初始化控制器
        - shutdown: 关闭控制器
        - on_event: 订阅事件
    """
    
    def __init__(
        self,
        context: Optional[AppContext] = None,
        event_bus: Optional["EventBus"] = None,
    ) -> None:
        self._context = context
        self._event_bus = event_bus
        self._initialized = False
        self._subscriptions: List[Callable[[], None]] = []
    
    def initialize(self) -> None:
        """
        初始化控制器。
        
        子类应重写此方法以执行初始化逻辑。
        """
        if self._initialized:
            return
        self._do_initialize()
        self._initialized = True
    
    def shutdown(self) -> None:
        """
        关闭控制器。
        
        清理资源并取消事件订阅。
        """
        for unsubscribe in self._subscriptions:
            try:
                unsubscribe()
            except Exception as e:
                logger.warning("Failed to unsubscribe: %s", e)
        self._subscriptions.clear()
        self._do_shutdown()
        self._initialized = False
    
    def _do_initialize(self) -> None:
        """子类实现的初始化逻辑。"""
        pass
    
    def _do_shutdown(self) -> None:
        """子类实现的关闭逻辑。"""
        pass
    
    def _subscribe_event(
        self,
        event_type: str,
        handler: Callable[[Any], None],
        priority: int = 0,
    ) -> None:
        """
        订阅事件并记录订阅以便清理。
        
        Args:
            event_type: 事件类型
            handler: 事件处理器
            priority: 优先级
        """
        if self._event_bus:
            unsubscribe = self._event_bus.subscribe(event_type, handler, priority)
            self._subscriptions.append(unsubscribe)


class AnalysisController(ControllerBase):
    """
    分析控制器。
    
    负责崩溃日志分析的核心逻辑。
    
    Attributes:
        _detector_registry: 检测器注册表
        _cache: 分析结果缓存
        _cache_max_size: 缓存最大大小
    
    方法:
        - analyze: 分析崩溃日志
        - analyze_async: 异步分析
        - clear_cache: 清除缓存
        - get_cached_result: 获取缓存结果
    
    Example:
        >>> controller = AnalysisController(detector_registry, event_bus)
        >>> results = controller.analyze(crash_log)
        >>> for result in results:
        ...     print(f"{result.detector}: {result.issues}")
    """
    
    def __init__(
        self,
        detector_registry: Optional["DetectorRegistry"] = None,
        event_bus: Optional["EventBus"] = None,
        database: Optional["DatabaseManager"] = None,
    ) -> None:
        super().__init__(event_bus=event_bus)
        self._detector_registry = detector_registry
        self._database = database
        self._cache: Dict[str, List["DetectionResult"]] = {}
        self._cache_max_size = 100
        self._analysis_hooks: List[Callable[[str, List["DetectionResult"]], None]] = []
    
    def _do_initialize(self) -> None:
        """初始化分析控制器。"""
        from mca_core.events import EventTypes
        
        self._subscribe_event(
            EventTypes.ANALYSIS_START,
            self._on_analysis_start,
        )
    
    def _on_analysis_start(self, event: Any) -> None:
        """处理分析开始事件。"""
        logger.debug("Analysis started: %s", event.payload.get("file_path", "unknown"))
    
    def analyze(
        self,
        crash_log: str,
        use_cache: bool = True,
        parallel: bool = True,
    ) -> List["DetectionResult"]:
        """
        分析崩溃日志。
        
        Args:
            crash_log: 崩溃日志文本
            use_cache: 是否使用缓存
            parallel: 是否并行执行检测器
            
        Returns:
            检测结果列表
        """
        import hashlib
        
        cache_key = hashlib.md5(crash_log.encode()).hexdigest() if use_cache else None
        
        if cache_key and cache_key in self._cache:
            logger.debug("Cache hit for analysis")
            return self._cache[cache_key]
        
        if self._detector_registry is None:
            from mca_core.detectors import DetectorRegistry
            self._detector_registry = DetectorRegistry.get_instance()
        
        from mca_core.detectors.contracts import AnalysisContext
        
        context = AnalysisContext(analyzer=None, crash_log=crash_log)
        
        if parallel:
            results = self._detector_registry.run_all_parallel(None)
        else:
            results = self._detector_registry.run_all(None)
        
        if cache_key:
            self._add_to_cache(cache_key, results)
        
        for hook in self._analysis_hooks:
            try:
                hook(crash_log, results)
            except Exception as e:
                logger.warning("Analysis hook failed: %s", e)
        
        return results
    
    def analyze_async(
        self,
        crash_log: str,
        callback: Callable[[List["DetectionResult"]], None],
        use_cache: bool = True,
        parallel: bool = True,
    ) -> None:
        """
        异步分析崩溃日志。
        
        Args:
            crash_log: 崩溃日志文本
            callback: 完成回调
            use_cache: 是否使用缓存
            parallel: 是否并行执行
        """
        from mca_core.threading_utils import submit_task
        
        def _analyze() -> None:
            results = self.analyze(crash_log, use_cache=use_cache, parallel=parallel)
            callback(results)
        
        submit_task(_analyze)
    
    def _add_to_cache(self, key: str, results: List["DetectionResult"]) -> None:
        """添加结果到缓存。"""
        if len(self._cache) >= self._cache_max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[key] = results
    
    def clear_cache(self) -> None:
        """清除分析缓存。"""
        self._cache.clear()
    
    def get_cached_result(self, cache_key: str) -> Optional[List["DetectionResult"]]:
        """获取缓存的分析结果。"""
        return self._cache.get(cache_key)
    
    def add_analysis_hook(
        self,
        hook: Callable[[str, List["DetectionResult"]], None],
    ) -> Callable[[], None]:
        """
        添加分析钩子。
        
        Args:
            hook: 钩子函数，接收 (crash_log, results) 参数
            
        Returns:
            移除钩子的函数
        """
        self._analysis_hooks.append(hook)
        
        def remove() -> None:
            if hook in self._analysis_hooks:
                self._analysis_hooks.remove(hook)
        
        return remove


class FileController(ControllerBase):
    """
    文件操作控制器。
    
    负责文件加载、保存和导出功能。
    
    Attributes:
        _log_service: 日志服务
        _history: 文件历史
    
    方法:
        - load_file: 加载文件
        - save_file: 保存文件
        - export_results: 导出分析结果
        - get_history: 获取文件历史
    """
    
    def __init__(
        self,
        log_service: Optional["LogService"] = None,
        event_bus: Optional["EventBus"] = None,
    ) -> None:
        super().__init__(event_bus=event_bus)
        self._log_service = log_service
        self._history: List[Dict[str, Any]] = []
        self._max_history = 100
    
    def load_file(self, file_path: str) -> str:
        """
        加载文件内容。
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件内容
            
        Raises:
            FileNotFoundError: 文件不存在
            IOError: 读取失败
        """
        import os
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        
        self._add_to_history(file_path)
        
        return content
    
    def save_file(self, file_path: str, content: str) -> None:
        """
        保存文件内容。
        
        Args:
            file_path: 文件路径
            content: 文件内容
        """
        import os
        
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
    
    def export_results(
        self,
        file_path: str,
        results: List["DetectionResult"],
        format: str = "json",
    ) -> None:
        """
        导出分析结果。
        
        Args:
            file_path: 导出文件路径
            results: 分析结果
            format: 导出格式 (json, csv, txt)
        """
        import json
        import csv
        
        if format == "json":
            data = [
                {
                    "detector": r.detector,
                    "message": r.message,
                    "cause_label": r.cause_label,
                    "metadata": r.metadata,
                }
                for r in results
            ]
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        
        elif format == "csv":
            with open(file_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["detector", "message", "cause_label"])
                for r in results:
                    writer.writerow([r.detector, r.message, r.cause_label or ""])
        
        else:
            with open(file_path, "w", encoding="utf-8") as f:
                for r in results:
                    f.write(f"=== {r.detector} ===\n")
                    f.write(f"{r.message}\n")
                    if r.cause_label:
                        f.write(f"Cause: {r.cause_label}\n")
                    f.write("\n")
    
    def _add_to_history(self, file_path: str) -> None:
        """添加文件到历史记录。"""
        import os
        from datetime import datetime
        
        entry = {
            "path": file_path,
            "name": os.path.basename(file_path),
            "time": datetime.now().isoformat(),
        }
        
        self._history.insert(0, entry)
        
        if len(self._history) > self._max_history:
            self._history = self._history[:self._max_history]
    
    def get_history(self) -> List[Dict[str, Any]]:
        """获取文件历史。"""
        return list(self._history)
    
    def clear_history(self) -> None:
        """清除文件历史。"""
        self._history.clear()


class UIController(ControllerBase):
    """
    UI 控制器。
    
    负责 UI 状态管理和更新。
    
    方法:
        - update_status: 更新状态栏
        - show_progress: 显示进度
        - hide_progress: 隐藏进度
        - show_message: 显示消息
    """
    
    def __init__(
        self,
        event_bus: Optional["EventBus"] = None,
    ) -> None:
        super().__init__(event_bus=event_bus)
        self._status_handlers: List[Callable[[str], None]] = []
        self._progress_handlers: List[Callable[[float, str], None]] = []
    
    def register_status_handler(self, handler: Callable[[str], None]) -> None:
        """注册状态更新处理器。"""
        self._status_handlers.append(handler)
    
    def register_progress_handler(self, handler: Callable[[float, str], None]) -> None:
        """注册进度更新处理器。"""
        self._progress_handlers.append(handler)
    
    def update_status(self, message: str) -> None:
        """更新状态栏。"""
        for handler in self._status_handlers:
            try:
                handler(message)
            except Exception as e:
                logger.warning("Status handler failed: %s", e)
    
    def show_progress(self, value: float, message: str = "") -> None:
        """显示进度。"""
        for handler in self._progress_handlers:
            try:
                handler(value, message)
            except Exception as e:
                logger.warning("Progress handler failed: %s", e)
    
    def hide_progress(self) -> None:
        """隐藏进度。"""
        self.show_progress(1.0, "")
    
    def show_message(
        self,
        title: str,
        message: str,
        level: str = "info",
    ) -> None:
        """
        显示消息。
        
        Args:
            title: 消息标题
            message: 消息内容
            level: 消息级别 (info, warning, error)
        """
        from mca_core.events import EventTypes, AnalysisEvent
        
        if self._event_bus:
            self._event_bus.publish(
                AnalysisEvent(
                    type=EventTypes.UI_UPDATE,
                    payload={
                        "action": "show_message",
                        "title": title,
                        "message": message,
                        "level": level,
                    },
                )
            )


class ControllerRegistry:
    """
    控制器注册表。
    
    管理所有控制器的创建和生命周期。
    
    方法:
        - register: 注册控制器
        - get: 获取控制器
        - initialize_all: 初始化所有控制器
        - shutdown_all: 关闭所有控制器
    
    Example:
        >>> registry = ControllerRegistry()
        >>> registry.register("analysis", AnalysisController)
        >>> analysis = registry.get("analysis")
    """
    
    def __init__(self) -> None:
        self._controllers: Dict[str, ControllerBase] = {}
        self._factories: Dict[str, Callable[[], ControllerBase]] = {}
    
    def register(
        self,
        name: str,
        controller_class: type,
        **kwargs: Any,
    ) -> None:
        """
        注册控制器。
        
        Args:
            name: 控制器名称
            controller_class: 控制器类
            **kwargs: 初始化参数
        """
        self._factories[name] = lambda: controller_class(**kwargs)
    
    def register_instance(self, name: str, controller: ControllerBase) -> None:
        """
        注册控制器实例。
        
        Args:
            name: 控制器名称
            controller: 控制器实例
        """
        self._controllers[name] = controller
    
    def get(self, name: str) -> Optional[ControllerBase]:
        """
        获取控制器。
        
        如果控制器尚未创建，则使用工厂创建。
        
        Args:
            name: 控制器名称
            
        Returns:
            控制器实例，如果不存在返回 None
        """
        if name not in self._controllers and name in self._factories:
            controller = self._factories[name]()
            controller.initialize()
            self._controllers[name] = controller
        
        return self._controllers.get(name)
    
    def get_or_create(self, name: str, controller_class: type, **kwargs: Any) -> ControllerBase:
        """
        获取或创建控制器。
        
        Args:
            name: 控制器名称
            controller_class: 控制器类
            **kwargs: 初始化参数
            
        Returns:
            控制器实例
        """
        if name not in self._controllers:
            controller = controller_class(**kwargs)
            controller.initialize()
            self._controllers[name] = controller
        
        return self._controllers[name]
    
    def initialize_all(self) -> None:
        """初始化所有控制器。"""
        for controller in self._controllers.values():
            controller.initialize()
    
    def shutdown_all(self) -> None:
        """关闭所有控制器。"""
        for controller in self._controllers.values():
            controller.shutdown()
        self._controllers.clear()
    
    def has(self, name: str) -> bool:
        """检查控制器是否存在。"""
        return name in self._controllers or name in self._factories
