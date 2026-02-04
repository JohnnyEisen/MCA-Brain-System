from __future__ import annotations
import threading
from typing import Any, Callable, Dict, List


class ThreadSafeState:
    def __init__(self):
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {}
        self._callbacks: List[Callable[[str, Any, Any], None]] = []

    def subscribe(self, callback: Callable[[str, Any, Any], None]) -> None:
        self._callbacks.append(callback)

    def update(self, key, value):
        with self._lock:
            old = self._data.get(key)
            self._data[key] = value
            self._notify(key, old, value)

    def get(self, key, default=None):
        with self._lock:
            return self._data.get(key, default)

    def _notify(self, key, old_value, new_value):
        for cb in self._callbacks:
            try:
                cb(key, old_value, new_value)
            except Exception:
                continue
