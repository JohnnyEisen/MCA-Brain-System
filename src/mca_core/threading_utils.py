"""
线程工具模块

提供可复用的后台工作线程和重复任务执行器。

模块说明:
    本模块提供全局线程池管理和后台任务执行工具。
    
    主要组件:
        - ThreadPoolManager: 统一线程池管理器（推荐使用）
        - get_global_pool: 获取全局线程池（懒加载单例，向后兼容）
        - set_pool_size: 设置全局线程池大小
        - submit_task: 向全局线程池提交任务
        - run_in_thread: 在后台线程中运行函数
        - RepeatingWorker: 重复执行任务的后台工作线程
        - BackgroundWatcher: 文件/配置变更监视器
"""

from __future__ import annotations

import atexit
import logging
import multiprocessing
import os
import threading
import time
from concurrent.futures import Executor, Future, ProcessPoolExecutor, ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 统一线程池管理器 - Unified Thread Pool Manager
# ============================================================

class ThreadPoolManager:
    """
    统一线程池管理器（单例模式）。
    
    提供全局线程池和进程池的统一管理，支持：
        - 多个命名线程池
        - 进程池管理
        - 统一资源清理
        - 动态配置
    
    Attributes:
        default_max_workers: 默认线程池大小
    
    方法:
        - get_instance: 获取单例实例
        - get_pool: 获取或创建命名线程池
        - get_process_pool: 获取进程池
        - submit: 提交任务到指定池
        - shutdown_all: 关闭所有池
    
    Example:
        >>> manager = ThreadPoolManager.get_instance()
        >>> future = manager.submit("analysis", my_func, arg1, arg2)
        >>> result = future.result()
    """
    
    _instance: Optional["ThreadPoolManager"] = None
    _lock: threading.Lock = threading.Lock()
    
    def __new__(cls) -> "ThreadPoolManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        if self._initialized:
            return
        
        self._pools: Dict[str, ThreadPoolExecutor] = {}
        self._process_pool: Optional[ProcessPoolExecutor] = None
        self._pool_configs: Dict[str, int] = {}
        self._shutdown_registered = False
        
        cpu_count = os.cpu_count() or 4
        self._default_max_workers = min(cpu_count * 4, 32)
        self._default_process_workers = min(cpu_count, 8)
        
        self._initialized = True
    
    @classmethod
    def get_instance(cls) -> "ThreadPoolManager":
        """获取单例实例。"""
        return cls()
    
    @classmethod
    def reset(cls) -> None:
        """重置单例（仅用于测试）。"""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.shutdown_all()
                cls._instance = None
    
    @property
    def default_max_workers(self) -> int:
        """获取默认线程池大小。"""
        return self._default_max_workers
    
    @default_max_workers.setter
    def default_max_workers(self, value: int) -> None:
        """设置默认线程池大小（仅影响新创建的池）。"""
        self._default_max_workers = max(1, value)
    
    def get_pool(
        self, 
        name: str = "default", 
        max_workers: Optional[int] = None
    ) -> ThreadPoolExecutor:
        """
        获取或创建命名线程池。
        
        Args:
            name: 线程池名称
            max_workers: 最大工作线程数（仅创建时生效）
            
        Returns:
            ThreadPoolExecutor 实例
        """
        if name not in self._pools:
            workers = max_workers or self._default_max_workers
            self._pools[name] = ThreadPoolExecutor(
                max_workers=workers,
                thread_name_prefix=f"MCA-{name}"
            )
            self._pool_configs[name] = workers
            self._register_shutdown()
        
        return self._pools[name]
    
    def get_process_pool(
        self, 
        max_workers: Optional[int] = None
    ) -> Optional[ProcessPoolExecutor]:
        """
        获取或创建进程池。
        
        Args:
            max_workers: 最大进程数（仅创建时生效）
            
        Returns:
            ProcessPoolExecutor 实例，如果配置为 0 则返回 None
        """
        if self._process_pool is None:
            workers = max_workers or self._default_process_workers
            if workers > 0:
                self._process_pool = ProcessPoolExecutor(max_workers=workers)
                self._register_shutdown()
        
        return self._process_pool
    
    def submit(
        self,
        pool_name: str,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Future[Any]:
        """
        提交任务到指定线程池。
        
        Args:
            pool_name: 线程池名称
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            Future 对象
        """
        pool = self.get_pool(pool_name)
        return pool.submit(func, *args, **kwargs)
    
    def submit_to_process(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Optional[Future[Any]]:
        """
        提交任务到进程池。
        
        Args:
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            Future 对象，如果进程池不可用则返回 None
        """
        pool = self.get_process_pool()
        if pool is None:
            logger.warning("进程池不可用，任务未提交")
            return None
        return pool.submit(func, *args, **kwargs)
    
    def get_executor(self, pool_name: str = "default") -> Executor:
        """
        获取 Executor 接口（兼容 BrainCore）。
        
        Args:
            pool_name: 线程池名称
            
        Returns:
            Executor 实例
        """
        return self.get_pool(pool_name)
    
    def shutdown_pool(self, name: str, wait: bool = False) -> None:
        """
        关闭指定线程池。
        
        Args:
            name: 线程池名称
            wait: 是否等待任务完成
        """
        if name in self._pools:
            self._pools[name].shutdown(wait=wait, cancel_futures=not wait)
            del self._pools[name]
            if name in self._pool_configs:
                del self._pool_configs[name]
    
    def shutdown_all(self, wait: bool = False) -> None:
        """
        关闭所有线程池和进程池。
        
        Args:
            wait: 是否等待任务完成
        """
        for name in list(self._pools.keys()):
            self.shutdown_pool(name, wait=wait)
        
        if self._process_pool is not None:
            self._process_pool.shutdown(wait=wait, cancel_futures=not wait)
            self._process_pool = None
    
    def _register_shutdown(self) -> None:
        """注册退出时的清理函数。"""
        if not self._shutdown_registered:
            atexit.register(self.shutdown_all)
            self._shutdown_registered = True
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取线程池统计信息。
        
        Returns:
            包含各线程池状态的字典
        """
        return {
            "pools": {
                name: {"max_workers": config}
                for name, config in self._pool_configs.items()
            },
            "process_pool": {
                "enabled": self._process_pool is not None,
                "max_workers": self._default_process_workers if self._process_pool else 0
            },
            "default_max_workers": self._default_max_workers
        }


# ============================================================
# 全局线程池管理 - Global Thread Pool Management (向后兼容)
# ============================================================

_global_pool: Optional[ThreadPoolExecutor] = None
_pool_lock: threading.Lock = threading.Lock()
_pool_max_workers: Optional[int] = None


def get_global_pool() -> ThreadPoolExecutor:
    """
    获取全局线程池（懒加载单例）。
    
    推荐使用 ThreadPoolManager.get_instance().get_pool() 替代。
    
    Returns:
        全局 ThreadPoolExecutor 实例
    """
    global _global_pool, _pool_max_workers

    if _global_pool is None:
        with _pool_lock:
            if _global_pool is None:
                manager = ThreadPoolManager.get_instance()
                _global_pool = manager.get_pool("legacy")
                if _pool_max_workers is not None:
                    pass

    return _global_pool


def set_pool_size(max_workers: int) -> None:
    """
    设置全局线程池大小（需在首次使用前调用）。
    
    Args:
        max_workers: 最大工作线程数
        
    Note:
        如果线程池已初始化，此函数将不会生效并输出警告日志。
    """
    global _pool_max_workers
    if _global_pool is not None:
        logger.warning("线程池已初始化，无法修改大小")
        return
    _pool_max_workers = max_workers
    ThreadPoolManager.get_instance().default_max_workers = max_workers


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
    """
    向全局线程池提交任务。
    
    推荐使用 ThreadPoolManager.get_instance().submit() 替代。
    
    Args:
        func: 要执行的函数
        *args: 函数位置参数
        **kwargs: 函数关键字参数
        
    Returns:
        Future 对象，可用于获取结果或取消任务
    """
    return get_global_pool().submit(func, *args, **kwargs)


def run_in_thread(
    func: Callable[[], None],
    *,
    name: Optional[str] = None,
    daemon: bool = True,
) -> threading.Thread:
    """
    在后台线程中运行函数（兼容旧代码，推荐使用 submit_task）。
    
    注意：此函数仍创建新线程以保持向后兼容。
    对于新代码，建议使用 submit_task() 提交到线程池。
    
    Args:
        func: 要运行的函数
        name: 线程名称
        daemon: 是否为守护线程
        
    Returns:
        启动的线程对象
    """
    thread = threading.Thread(target=func, name=name, daemon=daemon)
    thread.start()
    return thread


# ============================================================
# 重复任务执行器 - Repeating Task Executor
# ============================================================

class RepeatingWorker:
    """
    重复执行任务的后台工作线程。
    
    支持以下功能:
        - 可配置的执行间隔
        - 优雅停止
        - 错误回调
        - 初始延迟
    
    Attributes:
        is_running: 是否正在运行
    
    方法:
        - start: 启动工作线程
        - stop: 停止工作线程
    
    Example:
        >>> def my_task():
        ...     print("执行任务")
        >>> worker = RepeatingWorker(my_task, interval=5.0)
        >>> worker.start()
        >>> # ... 稍后
        >>> worker.stop()
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
        """
        初始化重复工作器。
        
        Args:
            target: 要重复执行的目标函数
            interval: 执行间隔（秒）
            name: 线程名称
            on_error: 错误回调函数
            initial_delay: 启动后首次执行的延迟（秒）
        """
        self._target: Callable[[], None] = target
        self._interval: float = interval
        self._name: str = name or f"RepeatingWorker-{id(self)}"
        self._on_error: Optional[Callable[[Exception], None]] = on_error
        self._initial_delay: float = initial_delay

        self._stop_event: threading.Event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def is_running(self) -> bool:
        """
        检查工作线程是否正在运行。
        
        Returns:
            如果线程存在且存活则返回 True
        """
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
                            logger.exception("Error in RepeatingWorker error callback")
                    else:
                        logger.error("RepeatingWorker %s error: %s", self._name, e)

                self._stop_event.wait(self._interval)

        self._thread = threading.Thread(target=run, name=self._name, daemon=True)
        self._thread.start()

    def stop(self, timeout: Optional[float] = None) -> None:
        """
        停止工作线程。
        
        Args:
            timeout: 等待线程结束的超时时间（秒）
        """
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None


# ============================================================
# 文件监视器 - File Watcher
# ============================================================

class BackgroundWatcher:
    """
    文件/配置变更监视器基类。
    
    提供文件修改时间检测和变更回调。
    
    Attributes:
        file_path: 监视的文件路径
    
    方法:
        - start: 启动监视
        - stop: 停止监视
    
    Example:
        >>> def on_file_change():
        ...     print("文件已更改")
        >>> watcher = BackgroundWatcher("/path/to/file", on_file_change)
        >>> watcher.start()
        >>> # ... 稍后
        >>> watcher.stop()
    """

    def __init__(
        self,
        file_path: str,
        on_change: Callable[[], None],
        poll_interval: float = 1.0,
    ) -> None:
        """
        初始化文件监视器。
        
        Args:
            file_path: 要监视的文件路径
            on_change: 文件变更时的回调函数
            poll_interval: 轮询间隔（秒）
        """
        self._file_path: str = file_path
        self._on_change: Callable[[], None] = on_change
        self._poll_interval: float = poll_interval

        self._last_mtime: Optional[float] = None
        self._worker: Optional[RepeatingWorker] = None

    @property
    def file_path(self) -> str:
        """
        获取监视的文件路径。
        
        Returns:
            文件路径字符串
        """
        return self._file_path

    def _check_file(self) -> None:
        """检查文件是否变更。"""
        try:
            mtime = os.path.getmtime(self._file_path)
            if self._last_mtime is None:
                self._last_mtime = mtime
            elif mtime > self._last_mtime:
                self._last_mtime = mtime
                self._on_change()
        except OSError:
            pass

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
