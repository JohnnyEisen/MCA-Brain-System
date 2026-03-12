"""线程工具模块。

提供可复用的后台工作线程和重复任务执行器。
"""
from __future__ import annotations

import atexit
import logging
import os
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# 全局线程池（懒加载）
_global_pool: ThreadPoolExecutor | None = None
_pool_lock = threading.Lock()
_pool_max_workers: int | None = None


def get_global_pool() -> ThreadPoolExecutor:
    """获取全局线程池（懒加载单例）。

    线程池大小默认为 min(CPU核心数 * 4, 32)。

    Returns:
        全局 ThreadPoolExecutor 实例。
    """
    global _global_pool, _pool_max_workers

    if _global_pool is None:
        with _pool_lock:
            if _global_pool is None:
                if _pool_max_workers is None:
                    cpu_count = os.cpu_count() or 4
                    _pool_max_workers = min(cpu_count * 4, 32)
                _global_pool = ThreadPoolExecutor(
                    max_workers=_pool_max_workers,
                    thread_name_prefix="MCA-Pool"
                )
                atexit.register(_shutdown_pool)

    return _global_pool


def set_pool_size(max_workers: int) -> None:
    """设置全局线程池大小（需在首次使用前调用）。

    Args:
        max_workers: 最大工作线程数。
    """
    global _pool_max_workers
    if _global_pool is not None:
        logger.warning("线程池已初始化，无法修改大小")
        return
    _pool_max_workers = max_workers


def _shutdown_pool() -> None:
    """关闭全局线程池（退出时自动调用）。"""
    global _global_pool
    if _global_pool is not None:
        _global_pool.shutdown(wait=False, cancel_futures=True)
        _global_pool = None


def submit_task(
    func: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> Future[Any]:
    """向全局线程池提交任务。

    Args:
        func: 要执行的函数。
        *args: 函数位置参数。
        **kwargs: 函数关键字参数。

    Returns:
        Future 对象，可用于获取结果或取消任务。
    """
    return get_global_pool().submit(func, *args, **kwargs)


def run_in_thread(
    func: Callable[[], None],
    *,
    name: Optional[str] = None,
    daemon: bool = True,
) -> threading.Thread:
    """在后台线程中运行函数（兼容旧代码，推荐使用 submit_task）。

    注意：此函数仍创建新线程以保持向后兼容。
    对于新代码，建议使用 submit_task() 提交到线程池。

    Args:
        func: 要运行的函数。
        name: 线程名称。
        daemon: 是否为守护线程。

    Returns:
        启动的线程对象。
    """
    thread = threading.Thread(target=func, name=name, daemon=daemon)
    thread.start()
    return thread


class RepeatingWorker:
    """重复执行任务的后台工作线程。

    支持：
    - 可配置的执行间隔
    - 优雅停止
    - 错误回调
    - 指数退避（可选）
    """

    def __init__(
        self,
        target: Callable[[], None],
        interval: float,
        *,
        name: Optional[str] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        initial_delay: float = 0.0,
    ) -> None:
        """初始化重复工作器。

        Args:
            target: 要重复执行的目标函数。
            interval: 执行间隔（秒）。
            name: 线程名称。
            on_error: 错误回调函数。
            initial_delay: 启动后首次执行的延迟（秒）。
        """
        self._target = target
        self._interval = interval
        self._name = name or f"RepeatingWorker-{id(self)}"
        self._on_error = on_error
        self._initial_delay = initial_delay

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        """是否正在运行。"""
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """启动工作线程。"""
        if self._thread is not None:
            return

        self._stop_event.clear()

        def run() -> None:
            if self._initial_delay > 0:
                time.sleep(self._initial_delay)

            while not self._stop_event.is_set():
                try:
                    self._target()
                except Exception as e:
                    if self._on_error:
                        try:
                            self._on_error(e)
                        except Exception:
                            logger.exception(
                                "Error in RepeatingWorker error callback"
                            )
                    else:
                        logger.error(
                            "RepeatingWorker %s error: %s", self._name, e
                        )

                self._stop_event.wait(self._interval)

        self._thread = threading.Thread(target=run, name=self._name, daemon=True)
        self._thread.start()

    def stop(self, timeout: Optional[float] = None) -> None:
        """停止工作线程。

        Args:
            timeout: 等待线程结束的超时时间。
        """
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None


class BackgroundWatcher:
    """文件/配置变更监视器基类。

    提供文件修改时间检测和变更回调。
    """

    def __init__(
        self,
        file_path: str,
        on_change: Callable[[], None],
        poll_interval: float = 1.0,
    ) -> None:
        """初始化文件监视器。

        Args:
            file_path: 要监视的文件路径。
            on_change: 文件变更时的回调函数。
            poll_interval: 轮询间隔（秒）。
        """
        self._file_path = file_path
        self._on_change = on_change
        self._poll_interval = poll_interval

        self._last_mtime: float | None = None
        self._worker: RepeatingWorker | None = None

    def _check_file(self) -> None:
        """检查文件是否变更。"""
        try:
            import os

            mtime = os.path.getmtime(self._file_path)
            if self._last_mtime is None:
                self._last_mtime = mtime
            elif mtime > self._last_mtime:
                self._last_mtime = mtime
                self._on_change()
        except Exception:
            pass  # 文件不存在或无法访问

    def start(self) -> None:
        """启动监视。"""
        if self._worker is not None:
            return

        self._worker = RepeatingWorker(
            target=self._check_file,
            interval=self._poll_interval,
            name=f"FileWatcher-{self._file_path}",
        )
        self._worker.start()

    def stop(self) -> None:
        """停止监视。"""
        if self._worker is not None:
            self._worker.stop()
            self._worker = None
