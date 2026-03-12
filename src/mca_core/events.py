"""事件总线模块。

提供事件发布/订阅机制，用于模块间解耦通信。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class AnalysisEvent:
    """分析事件数据类。

    Attributes:
        type: 事件类型。
        payload: 事件负载数据。
    """

    type: str
    payload: dict[str, Any]


class EventTypes:
    """事件类型常量。"""

    ANALYSIS_START: str = "analysis_start"
    ANALYSIS_PROGRESS: str = "analysis_progress"
    DETECTOR_COMPLETE: str = "detector_complete"
    UI_UPDATE: str = "ui_update"
    ANALYSIS_COMPLETE: str = "analysis_complete"
    ANALYSIS_ERROR: str = "analysis_error"


class EventBus:
    """事件总线：管理事件订阅和发布。"""

    def __init__(self) -> None:
        """初始化事件总线。"""
        self._subscribers: dict[str, list[Callable[[AnalysisEvent], None]]] = {}

    def subscribe(
        self, event_type: str, handler: Callable[[AnalysisEvent], None]
    ) -> None:
        """订阅事件。

        Args:
            event_type: 事件类型。
            handler: 事件处理函数。
        """
        self._subscribers.setdefault(event_type, []).append(handler)

    def unsubscribe(
        self, event_type: str, handler: Callable[[AnalysisEvent], None]
    ) -> None:
        """取消订阅事件。

        Args:
            event_type: 事件类型。
            handler: 要移除的处理函数。
        """
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                h for h in self._subscribers[event_type] if h != handler
            ]

    def publish(self, event: AnalysisEvent) -> None:
        """发布事件。

        Args:
            event: 要发布的事件。
        """
        for handler in self._subscribers.get(event.type, []):
            try:
                handler(event)
            except Exception:
                continue
