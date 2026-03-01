"""进度报告工具模块。

提供进度监听和报告功能，用于分析和任务执行过程中的进度通知。
"""
from __future__ import annotations

from typing import Callable


class ProgressReporter:
    """进度报告器：管理进度监听器并广播进度事件。"""

    def __init__(self) -> None:
        """初始化进度报告器。"""
        self._listeners: list[Callable[[float, str], None]] = []

    def subscribe(self, listener: Callable[[float, str], None]) -> None:
        """订阅进度事件。

        Args:
            listener: 监听器函数，接收进度值(0.0-1.0)和消息字符串。
        """
        self._listeners.append(listener)

    def report(self, value: float, message: str = "") -> None:
        """报告当前进度。

        Args:
            value: 进度值，范围 0.0 到 1.0。
            message: 进度消息。
        """
        for listener in self._listeners:
            try:
                listener(value, message)
            except Exception:
                continue
