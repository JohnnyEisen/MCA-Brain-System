"""
日志服务模块

负责日志文本的存储、缓存、预处理及文件 IO。

类说明:
    - LogService: 日志管理服务，提供内存优化的日志处理
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import TYPE_CHECKING, Any, Callable, Iterator, Optional

if TYPE_CHECKING:
    from mca_core.security import InputSanitizer
    from mca_core.file_io import read_text_limited
    from mca_core.streaming import StreamingLogAnalyzer
    from mca_core.threading_utils import submit_task

from config.constants import DEFAULT_MAX_BYTES

logger = logging.getLogger(__name__)


class LogService:
    """
    日志管理服务。
    
    负责日志文本的存储、缓存、预处理及文件 IO。
    使用内存优化策略，避免同时持有多个副本。
    
    内存优化策略:
        - 使用单一缓存策略，避免同时持有多个副本
        - lower 和 lines 缓存互斥，不会同时存在
        - 支持 Iterator 模式流式访问，适合大文件
    
    类属性:
        CACHE_NONE: 无缓存状态
        CACHE_LOWER: 小写版本缓存状态
        CACHE_LINES: 行列表缓存状态
    
    Attributes:
        _crash_log: 崩溃日志文本
        file_path: 日志文件路径
        file_checksum: 文件校验和
        _cache_type: 当前缓存类型
        _cache_lower: 小写版本缓存
        _cache_lines: 行列表缓存
        _is_large_file: 是否为大文件标记
    
    方法:
        - set_log_text: 设置日志文本
        - get_text: 获取原始日志文本
        - get_lower: 获取小写版本日志
        - get_lines: 获取日志行列表
        - iter_lines: 流式迭代日志行
        - get_memory_usage: 获取内存使用情况
        - load_from_file_async: 异步加载文件
    """

    CACHE_NONE: int = 0
    CACHE_LOWER: int = 1
    CACHE_LINES: int = 2

    def __init__(self) -> None:
        """初始化日志服务。"""
        self._crash_log: str = ""
        self.file_path: str = ""
        self.file_checksum: Optional[str] = None

        self._cache_type: int = self.CACHE_NONE
        self._cache_lower: Optional[str] = None
        self._cache_lines: Optional[list[str]] = None

        self._is_large_file: bool = False

    def set_log_text(self, text: str) -> None:
        """
        设置新的日志内容并清空缓存。
        
        Args:
            text: 新的日志文本
        """
        self._crash_log = text or ""
        self._clear_cache()
        self._is_large_file = len(self._crash_log) > 10 * 1024 * 1024

    def _clear_cache(self) -> None:
        """清空所有缓存。"""
        self._cache_type = self.CACHE_NONE
        self._cache_lower = None
        self._cache_lines = None

    _invalidate_log_cache = _clear_cache

    def get_text(self) -> str:
        """
        获取原始日志文本。
        
        Returns:
            原始日志文本
        """
        return self._crash_log

    def get_lower(self) -> str:
        """
        获取小写版本的日志文本（延迟计算，独占缓存）。
        
        Returns:
            小写版本的日志文本
        """
        if self._cache_type != self.CACHE_LOWER or self._cache_lower is None:
            self._cache_lines = None
            self._cache_lower = self._crash_log.lower()
            self._cache_type = self.CACHE_LOWER
        return self._cache_lower

    def get_lines(self, lower: bool = False) -> list[str]:
        """
        获取日志行列表（延迟计算，独占缓存）。
        
        Args:
            lower: 是否返回小写版本的行列表
            
        Returns:
            日志行列表
            
        Note:
            此方法与 get_lower() 互斥，调用会清除另一种格式的缓存。
            对于大文件，建议使用 iter_lines() 流式访问。
        """
        target_type = self.CACHE_LINES if not lower else self.CACHE_LOWER

        if self._cache_type != target_type or self._cache_lines is None:
            if lower:
                self._cache_lines = None
                self._cache_lower = self._crash_log.lower()
                self._cache_type = self.CACHE_LOWER
                return self._cache_lower.splitlines()
            else:
                self._cache_lower = None
                self._cache_lines = self._crash_log.splitlines()
                self._cache_type = self.CACHE_LINES
                return self._cache_lines

        if lower and self._cache_lower:
            return self._cache_lower.splitlines()
        return self._cache_lines or []

    def iter_lines(self, lower: bool = False) -> Iterator[str]:
        """
        流式迭代日志行，不占用额外内存。
        
        Args:
            lower: 是否返回小写版本的行
            
        Yields:
            日志行字符串
            
        Note:
            适用于大文件场景，避免一次性创建完整行列表。
        """
        source = self._crash_log.lower() if lower else self._crash_log
        for line in source.splitlines():
            yield line

    def get_memory_usage(self) -> dict[str, int | bool | str]:
        """
        返回当前内存使用情况（用于调试/监控）。
        
        Returns:
            包含内存使用信息的字典
        """
        log_size = len(self._crash_log)
        cache_size = 0

        if self._cache_lower:
            cache_size += len(self._cache_lower)
        if self._cache_lines:
            cache_size += sum(len(line) for line in self._cache_lines[:100])

        return {
            "log_size_bytes": log_size,
            "cache_size_bytes": cache_size,
            "total_estimate_bytes": log_size + cache_size,
            "is_large_file": self._is_large_file,
            "cache_type": ["none", "lower", "lines"][self._cache_type]
        }

    def load_from_file_async(
        self,
        file_path: str,
        on_success: Callable[[], None],
        on_error: Callable[[Exception], None],
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> None:
        """
        异步加载文件内容（使用全局线程池）。
        
        Args:
            file_path: 文件路径
            on_success: 成功回调
            on_error: 错误回调
            progress_callback: 进度回调（可选）
        """
        from mca_core.threading_utils import submit_task

        def _task() -> None:
            try:
                self._load_from_file_sync(file_path, progress_callback)
                on_success()
            except Exception as e:
                on_error(e)

        submit_task(_task)

    def load_from_multiple_files_async(
        self,
        paths: list[str],
        on_success: Callable[[], None],
        on_error: Callable[[Exception], None]
    ) -> None:
        """
        异步加载多个文件（使用全局线程池）。
        
        Args:
            paths: 文件路径列表
            on_success: 成功回调
            on_error: 错误回调
        """
        from mca_core.threading_utils import submit_task

        def _task() -> None:
            try:
                self._load_multiple_files_sync(paths)
                on_success()
            except Exception as e:
                on_error(e)

        submit_task(_task)

    def _load_from_file_sync(
        self,
        file_path: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> None:
        """
        同步加载单个文件。
        
        Args:
            file_path: 文件路径
            progress_callback: 进度回调（可选）
        """
        from mca_core.security import InputSanitizer
        from mca_core.file_io import read_text_limited
        from mca_core.streaming import StreamingLogAnalyzer

        if not InputSanitizer.validate_file_path(file_path):
            raise ValueError("无效的文件路径")

        try:
            file_size = os.path.getsize(file_path)
        except OSError:
            file_size = 0

        data = ""
        if file_size > DEFAULT_MAX_BYTES:
            chunks: list[str] = []
            read_total = 0
            max_bytes = DEFAULT_MAX_BYTES

            def _on_chunk(chunk: Any) -> bool:
                nonlocal read_total
                if read_total >= max_bytes:
                    return False
                take = min(len(chunk.content), max_bytes - read_total)
                if take > 0:
                    chunks.append(chunk.content[:take])
                    read_total += take
                    if progress_callback:
                        try:
                            progress_callback(read_total / max_bytes, "加载日志中...")
                        except Exception:
                            pass
                return read_total < max_bytes

            StreamingLogAnalyzer(file_path, chunk_size=256 * 1024).analyze_incremental(_on_chunk)
            data = "".join(chunks)
        else:
            data = read_text_limited(file_path)

        self._update_state(data, file_path)

    def _load_multiple_files_sync(self, paths: list[str]) -> None:
        """
        同步加载多个文件并合并。
        
        Args:
            paths: 文件路径列表
        """
        from mca_core.security import InputSanitizer
        from mca_core.file_io import read_text_limited

        combined_log: list[str] = []
        total_size = 0
        sorted_paths = sorted(set(paths))

        valid_paths: list[str] = []

        for fpath in sorted_paths:
            if not InputSanitizer.validate_file_path(fpath):
                continue

            valid_paths.append(fpath)
            fname = os.path.basename(fpath)
            header = f"\n{'='*60}\n>>> JOINT ANALYSIS - FILE: {fname} <<<\n{'='*60}\n"

            try:
                fsize = os.path.getsize(fpath)
            except OSError:
                fsize = 0

            if total_size + fsize > DEFAULT_MAX_BYTES * 5:
                combined_log.append(header + f"\n[Skipped {fname}: Total size limit exceeded]")
                continue

            content = read_text_limited(fpath, max_bytes=DEFAULT_MAX_BYTES)
            combined_log.append(header)
            combined_log.append(content)
            total_size += len(content)

        full_data = "".join(combined_log)

        display_path = " + ".join([os.path.basename(p) for p in valid_paths[:3]])
        if len(valid_paths) > 3:
            display_path += f" ... (+{len(valid_paths)-3} more)"

        self._update_state(full_data, display_path)

    def _update_state(self, content: str, path_display: str) -> None:
        """
        更新内部状态。
        
        Args:
            content: 日志内容
            path_display: 显示路径
        """
        self._crash_log = content
        self.file_path = path_display
        try:
            self.file_checksum = hashlib.sha256(
                content.encode('utf-8', errors='ignore')
            ).hexdigest()
        except Exception:
            self.file_checksum = None
        self._clear_cache()
        self._is_large_file = len(content) > 10 * 1024 * 1024
