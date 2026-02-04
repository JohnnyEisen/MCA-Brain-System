from __future__ import annotations
from typing import Callable, List
from .errors import TaskCancelledError


class CancellableTask:
    def __init__(self):
        self._cancelled = False
        self._progress_callbacks: List[Callable[[float, str], None]] = []

    def on_progress(self, cb: Callable[[float, str], None]):
        self._progress_callbacks.append(cb)

    def cancel(self):
        self._cancelled = True

    def _report_progress(self, value: float = 0.0, message: str = ""):
        for cb in self._progress_callbacks:
            try:
                cb(value, message)
            except Exception:
                continue

    def run(self):
        while not self._cancelled and not self.is_complete():
            if self._cancelled:
                raise TaskCancelledError()
            self._report_progress()
            self._do_work()

    def is_complete(self) -> bool:
        return True

    def _do_work(self):
        return
