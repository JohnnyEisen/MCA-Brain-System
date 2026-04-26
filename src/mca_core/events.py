"""
事件总线模块

提供事件发布/订阅机制，用于模块间解耦通信。

模块说明:
    本模块实现了一个增强的事件总线，支持：
        - 事件发布和订阅
        - 优先级处理
        - 异步发布
        - 一次性订阅
        - 事件过滤
    
    主要组件:
        - AnalysisEvent: 分析事件数据类
        - EventTypes: 事件类型常量
        - EventBus: 事件总线，管理事件订阅和发布
        - EventHandler: 事件处理器封装
    
    使用示例:
        >>> bus = EventBus()
        >>> def on_complete(event):
        ...     print(f"分析完成: {event.payload}")
        >>> bus.subscribe(EventTypes.ANALYSIS_COMPLETE, on_complete, priority=10)
        >>> bus.publish(AnalysisEvent(EventTypes.ANALYSIS_COMPLETE, {"result": "ok"}))
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================
# 事件数据类 - Event Data Classes
# ============================================================

@dataclass
class AnalysisEvent:
    """
    分析事件数据类。
    
    用于封装事件类型和负载数据，在事件总线中传递。
    
    Attributes:
        type: 事件类型，应使用 EventTypes 中定义的常量
        payload: 事件负载数据字典
        timestamp: 事件时间戳（可选，自动生成）
        source: 事件来源标识（可选）
    
    Example:
        >>> event = AnalysisEvent("analysis_complete", {"result": "ok", "time": 1.5})
        >>> print(event.type)
        'analysis_complete'
    """
    
    type: str
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=lambda: __import__("time").time())
    source: Optional[str] = None

    def get(self, key: str, default: Any = None) -> Any:
        """从 payload 中获取值。"""
        return self.payload.get(key, default)


# ============================================================
# 事件类型常量 - Event Type Constants
# ============================================================

class EventTypes:
    """
    事件类型常量定义。
    
    提供标准化的事件类型字符串，用于事件订阅和发布。
    
    Attributes:
        ANALYSIS_START: 分析开始事件
        ANALYSIS_PROGRESS: 分析进度事件
        DETECTOR_COMPLETE: 检测器完成事件
        UI_UPDATE: UI 更新事件
        ANALYSIS_COMPLETE: 分析完成事件
        ANALYSIS_ERROR: 分析错误事件
        PLUGIN_LOADED: 插件加载事件
        CONFIG_CHANGED: 配置变更事件
    """
    
    ANALYSIS_START: str = "analysis_start"
    ANALYSIS_PROGRESS: str = "analysis_progress"
    DETECTOR_COMPLETE: str = "detector_complete"
    UI_UPDATE: str = "ui_update"
    ANALYSIS_COMPLETE: str = "analysis_complete"
    ANALYSIS_ERROR: str = "analysis_error"
    PLUGIN_LOADED: str = "plugin_loaded"
    CONFIG_CHANGED: str = "config_changed"


# ============================================================
# 事件处理器 - Event Handler
# ============================================================

@dataclass
class EventHandler:
    """
    事件处理器封装。
    
    封装处理函数及其元数据，支持优先级和过滤。
    
    Attributes:
        handler: 处理函数
        priority: 优先级（数值越大越先执行，默认 0）
        once: 是否为一次性订阅
        filter_func: 事件过滤函数（返回 True 表示处理该事件）
    """
    
    handler: Callable[[AnalysisEvent], None]
    priority: int = 0
    once: bool = False
    filter_func: Optional[Callable[[AnalysisEvent], bool]] = None
    
    def should_handle(self, event: AnalysisEvent) -> bool:
        """检查是否应该处理该事件。"""
        if self.filter_func is None:
            return True
        try:
            return self.filter_func(event)
        except Exception as e:
            logger.warning("Event filter failed: %s", e)
            return False
    
    def __call__(self, event: AnalysisEvent) -> None:
        """调用处理函数。"""
        self.handler(event)
    
    def __lt__(self, other: "EventHandler") -> bool:
        """用于排序，优先级高的排前面。"""
        return self.priority > other.priority


# ============================================================
# 事件总线 - Event Bus
# ============================================================

class EventBus:
    """
    事件总线：管理事件订阅和发布。
    
    实现发布/订阅模式，允许模块间松耦合通信。
    支持以下功能：
        - 多订阅者
        - 优先级处理
        - 异步发布
        - 一次性订阅
        - 事件过滤
        - 错误隔离
    
    Attributes:
        _subscribers: 事件类型到处理器列表的映射
        _async_queue: 异步事件队列
    
    方法:
        - subscribe: 订阅事件
        - subscribe_once: 一次性订阅
        - subscribe_with_filter: 带过滤的订阅
        - unsubscribe: 取消订阅
        - publish: 同步发布事件
        - publish_async: 异步发布事件
        - clear: 清除订阅
    
    Example:
        >>> bus = EventBus()
        >>> def handler(event):
        ...     print(f"收到事件: {event.type}")
        >>> bus.subscribe(EventTypes.ANALYSIS_START, handler, priority=10)
        >>> bus.publish(AnalysisEvent(EventTypes.ANALYSIS_START, {}))
        收到事件: analysis_start
    """

    def __init__(self) -> None:
        """初始化事件总线。"""
        self._subscribers: Dict[str, List[EventHandler]] = {}
        self._pending_removals: List[Tuple[str, EventHandler]] = []
        self._is_dispatching: bool = False

    def subscribe(
        self,
        event_type: str,
        handler: Callable[[AnalysisEvent], None],
        priority: int = 0,
    ) -> Callable[[], None]:
        """
        订阅事件。
        
        当指定类型的事件发布时，处理函数将被调用。
        
        Args:
            event_type: 事件类型，建议使用 EventTypes 中的常量
            handler: 事件处理函数，接收 AnalysisEvent 参数
            priority: 优先级（数值越大越先执行，默认 0）
            
        Returns:
            取消订阅的函数
            
        Example:
            >>> unsub = bus.subscribe("event", my_handler, priority=10)
            >>> # 稍后取消订阅
            >>> unsub()
        """
        event_handler = EventHandler(handler=handler, priority=priority)
        self._subscribers.setdefault(event_type, []).append(event_handler)
        self._subscribers[event_type].sort()
        
        def unsubscribe() -> None:
            self._remove_handler(event_type, event_handler)
        
        return unsubscribe

    def subscribe_once(
        self,
        event_type: str,
        handler: Callable[[AnalysisEvent], None],
        priority: int = 0,
    ) -> Callable[[], None]:
        """
        一次性订阅事件。
        
        处理函数只会在第一次事件发生时被调用，之后自动取消订阅。
        
        Args:
            event_type: 事件类型
            handler: 事件处理函数
            priority: 优先级
            
        Returns:
            取消订阅的函数
        """
        event_handler = EventHandler(handler=handler, priority=priority, once=True)
        self._subscribers.setdefault(event_type, []).append(event_handler)
        self._subscribers[event_type].sort()
        
        def unsubscribe() -> None:
            self._remove_handler(event_type, event_handler)
        
        return unsubscribe

    def subscribe_with_filter(
        self,
        event_type: str,
        handler: Callable[[AnalysisEvent], None],
        filter_func: Callable[[AnalysisEvent], bool],
        priority: int = 0,
    ) -> Callable[[], None]:
        """
        带过滤条件的事件订阅。
        
        只有当 filter_func 返回 True 时，处理函数才会被调用。
        
        Args:
            event_type: 事件类型
            handler: 事件处理函数
            filter_func: 过滤函数，接收事件并返回布尔值
            priority: 优先级
            
        Returns:
            取消订阅的函数
            
        Example:
            >>> bus.subscribe_with_filter(
            ...     EventTypes.ANALYSIS_PROGRESS,
            ...     on_progress,
            ...     lambda e: e.get("percent", 0) > 50
            ... )
        """
        event_handler = EventHandler(
            handler=handler,
            priority=priority,
            filter_func=filter_func,
        )
        self._subscribers.setdefault(event_type, []).append(event_handler)
        self._subscribers[event_type].sort()
        
        def unsubscribe() -> None:
            self._remove_handler(event_type, event_handler)
        
        return unsubscribe

    def subscribe_batch(
        self,
        subscriptions: List[Tuple[str, Callable[[AnalysisEvent], None]]],
        priority: int = 0,
    ) -> None:
        """
        批量订阅事件。
        
        一次性注册多个事件处理器，减少重复调用开销。
        
        Args:
            subscriptions: 订阅列表，每项为 (event_type, handler) 元组
            priority: 优先级（应用于所有处理器）
        
        Example:
            >>> bus.subscribe_batch([
            ...     (EventTypes.ANALYSIS_START, on_start),
            ...     (EventTypes.ANALYSIS_COMPLETE, on_complete),
            ... ])
        """
        for event_type, handler in subscriptions:
            event_handler = EventHandler(handler=handler, priority=priority)
            self._subscribers.setdefault(event_type, []).append(event_handler)
            self._subscribers[event_type].sort()

    def _remove_handler(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> None:
        """移除处理器（支持在分发过程中安全移除）。"""
        if self._is_dispatching:
            self._pending_removals.append((event_type, handler))
        else:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(handler)
                except ValueError:
                    pass

    def _process_pending_removals(self) -> None:
        """处理待移除的处理器。"""
        for event_type, handler in self._pending_removals:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(handler)
                except ValueError:
                    pass
        self._pending_removals.clear()

    def unsubscribe(
        self,
        event_type: str,
        handler: Callable[[AnalysisEvent], None],
    ) -> None:
        """
        取消订阅事件。
        
        从订阅列表中移除指定的处理函数。
        
        Args:
            event_type: 事件类型
            handler: 要移除的处理函数
        """
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                h for h in self._subscribers[event_type]
                if h.handler != handler
            ]

    def publish(self, event: AnalysisEvent) -> None:
        """
        同步发布事件。
        
        将事件分发给所有订阅了该事件类型的处理函数。
        处理函数按优先级顺序执行。
        如果某个处理函数抛出异常，不会影响其他处理函数的执行。
        
        Args:
            event: 要发布的事件对象
        """
        handlers = list(self._subscribers.get(event.type, []))
        if not handlers:
            return
        
        self._is_dispatching = True
        handlers_to_remove: List[EventHandler] = []
        
        try:
            for event_handler in handlers:
                if not event_handler.should_handle(event):
                    continue
                    
                try:
                    event_handler(event)
                except Exception as e:
                    logger.warning(
                        "Event handler failed for %s: %s",
                        event.type,
                        e,
                        exc_info=True,
                    )
                
                if event_handler.once:
                    handlers_to_remove.append(event_handler)
        finally:
            self._is_dispatching = False
            
            for h in handlers_to_remove:
                self._remove_handler(event.type, h)
            
            self._process_pending_removals()

    def publish_async(
        self,
        event: AnalysisEvent,
        executor: Optional[Any] = None,
    ) -> "Future[None]":
        """
        异步发布事件。
        
        在线程池中异步执行事件处理，不阻塞当前线程。
        
        Args:
            event: 要发布的事件对象
            executor: 可选的执行器（ThreadPoolExecutor）
            
        Returns:
            Future 对象，可用于等待完成
            
        Example:
            >>> future = bus.publish_async(event)
            >>> # 或使用线程池
            >>> from concurrent.futures import ThreadPoolExecutor
            >>> executor = ThreadPoolExecutor(max_workers=4)
            >>> future = bus.publish_async(event, executor=executor)
        """
        from concurrent.futures import ThreadPoolExecutor
        
        if executor is None:
            executor = ThreadPoolExecutor(max_workers=1)
            return executor.submit(self._publish_async_wrapper, event, executor)
        else:
            return executor.submit(self.publish, event)

    def _publish_async_wrapper(
        self,
        event: AnalysisEvent,
        executor: Any,
    ) -> None:
        """异步发布的包装器，确保执行器正确关闭。"""
        try:
            self.publish(event)
        finally:
            if isinstance(executor, ThreadPoolExecutor):
                executor.shutdown(wait=False)

    async def publish_awaitable(self, event: AnalysisEvent) -> None:
        """
        在 asyncio 事件循环中发布事件。
        
        适用于异步应用场景。
        
        Args:
            event: 要发布的事件对象
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.publish, event)

    def clear(self, event_type: Optional[str] = None) -> None:
        """
        清除订阅。
        
        Args:
            event_type: 要清除的事件类型，如果为 None 则清除所有订阅
        """
        if event_type is None:
            self._subscribers.clear()
        elif event_type in self._subscribers:
            del self._subscribers[event_type]
        
        self._pending_removals.clear()

    def has_subscribers(self, event_type: str) -> bool:
        """
        检查是否有订阅者。
        
        Args:
            event_type: 事件类型
            
        Returns:
            如果有订阅者返回 True，否则返回 False
        """
        return bool(self._subscribers.get(event_type))

    def get_subscriber_count(self, event_type: Optional[str] = None) -> int:
        """
        获取订阅者数量。
        
        Args:
            event_type: 事件类型，如果为 None 则返回总数
            
        Returns:
            订阅者数量
        """
        if event_type is None:
            return sum(len(handlers) for handlers in self._subscribers.values())
        return len(self._subscribers.get(event_type, []))


# ============================================================
# 全局事件总线实例 - Global Event Bus Instance
# ============================================================

_global_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """
    获取全局事件总线实例。
    
    Returns:
        全局 EventBus 实例
    """
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = EventBus()
    return _global_event_bus


def reset_event_bus() -> None:
    """重置全局事件总线（仅用于测试）。"""
    global _global_event_bus
    if _global_event_bus is not None:
        _global_event_bus.clear()
        _global_event_bus = None
