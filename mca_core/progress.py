from __future__ import annotations
from typing import Callable, List


class ProgressReporter:
    def __init__(self):
        self._listeners: List[Callable[[float, str], None]] = []

    def subscribe(self, listener: Callable[[float, str], None]) -> None:
        self._listeners.append(listener)

    def report(self, value: float, message: str = "") -> None:
        for listener in self._listeners:
            try:
                listener(value, message)
            except Exception:
                continue
