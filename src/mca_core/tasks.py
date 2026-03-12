"""可取消任务模块。

提供可取消的任务基类，支持进度报告。
"""
from __future__ import annotations

from typing import Callable

from .errors import TaskCancelledError


class CancellableTask:
    """可取消的任务基类。

    支持进度回调和取消操作。
    """

    def __init__(self) -> None:
        """初始化任务。"""
        self._cancelled = False
        self._progress_callbacks: list[Callable[[float, str], None]] = []

    def on_progress(self, cb: Callable[[float, str], None]) -> None:
        """注册进度回调函数。

        Args:
            cb: 回调函数，接收 (进度值, 消息) 参数。
        """
        self._progress_callbacks.append(cb)

    def cancel(self) -> None:
        """取消任务。"""
        self._cancelled = True

    def _report_progress(self, value: float = 0.0, message: str = "") -> None:
        """报告进度给所有回调。

        Args:
            value: 进度值 (0.0 - 1.0)。
            message: 进度消息。
        """
        for cb in self._progress_callbacks:
            try:
                cb(value, message)
            except Exception:
                continue

    def run(self) -> None:
        """运行任务直到完成或取消。"""
        while not self._cancelled and not self.is_complete():
            if self._cancelled:
                raise TaskCancelledError()
            self._report_progress()
            self._do_work()

    def is_complete(self) -> bool:
        """检查任务是否完成。

        Returns:
            任务是否完成。
        """
        return True

    def _do_work(self) -> None:
        """执行单次工作迭代，由子类实现。"""
        return
