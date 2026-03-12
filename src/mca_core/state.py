"""线程安全状态管理模块。

提供线程安全的状态存储和变更通知机制。
"""
from __future__ import annotations

import threading
from typing import Any, Callable


class ThreadSafeState:
    """线程安全的状态容器，支持变更订阅。"""

    def __init__(self) -> None:
        """初始化状态容器。"""
        self._lock = threading.RLock()
        self._data: dict[str, Any] = {}
        self._callbacks: list[Callable[[str, Any, Any], None]] = []

    def subscribe(self, callback: Callable[[str, Any, Any], None]) -> None:
        """订阅状态变更事件。

        Args:
            callback: 回调函数，接收 (key, old_value, new_value) 参数。
        """
        self._callbacks.append(callback)

    def update(self, key: str, value: Any) -> None:
        """更新状态值。

        Args:
            key: 状态键名。
            value: 新值。
        """
        with self._lock:
            old = self._data.get(key)
            self._data[key] = value
            self._notify(key, old, value)

    def get(self, key: str, default: Any = None) -> Any:
        """获取状态值。

        Args:
            key: 状态键名。
            default: 默认值。

        Returns:
            状态值或默认值。
        """
        with self._lock:
            return self._data.get(key, default)

    def _notify(self, key: str, old_value: Any, new_value: Any) -> None:
        """通知所有订阅者状态变更。

        Args:
            key: 变更的键名。
            old_value: 旧值。
            new_value: 新值。
        """
        for cb in self._callbacks:
            try:
                cb(key, old_value, new_value)
            except Exception:
                continue
