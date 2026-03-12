import os
import hashlib
import threading
from typing import Optional, Callable, Iterator, Any

from mca_core.security import InputSanitizer
from mca_core.file_io import read_text_limited
from mca_core.streaming import StreamingLogAnalyzer
from mca_core.threading_utils import submit_task
from config.constants import DEFAULT_MAX_BYTES


class LogService:
    """负责日志文本的存储、缓存、预处理及文件IO。
    
    内存优化策略：
    - 使用单一缓存策略，避免同时持有多个副本
    - lower 和 lines 缓存互斥，不会同时存在
    - 支持 Iterator 模式流式访问，适合大文件
    """
    
    # 缓存策略：只缓存一种格式
    CACHE_NONE = 0      # 无缓存
    CACHE_LOWER = 1     # 缓存小写版本
    CACHE_LINES = 2     # 缓存行列表
    
    def __init__(self) -> None:
        self._crash_log: str = ""
        self.file_path: str = ""
        self.file_checksum: Optional[str] = None
        
        # 单一缓存策略：只保留一种格式的缓存
        self._cache_type: int = self.CACHE_NONE
        self._cache_lower: Optional[str] = None
        self._cache_lines: Optional[list[str]] = None
        
        # 大文件标记（超过阈值时使用流式处理建议）
        self._is_large_file: bool = False

    def set_log_text(self, text: str) -> None:
        """设置新的日志内容并清空缓存。"""
        self._crash_log = text or ""
        self._clear_cache()
        self._is_large_file = len(self._crash_log) > 10 * 1024 * 1024  # 10MB

    def _clear_cache(self) -> None:
        """清空所有缓存。"""
        self._cache_type = self.CACHE_NONE
        self._cache_lower = None
        self._cache_lines = None


    # 别名，保持向后兼容
    _invalidate_log_cache = _clear_cache

    def get_text(self) -> str:
        """获取原始日志文本。"""
        return self._crash_log

    def get_lower(self) -> str:
        """获取小写版本的日志文本（延迟计算，独占缓存）。"""
        if self._cache_type != self.CACHE_LOWER or self._cache_lower is None:
            # 清除其他格式的缓存，释放内存
            self._cache_lines = None


            self._cache_lower = self._crash_log.lower()
            self._cache_type = self.CACHE_LOWER
        return self._cache_lower

    def get_lines(self, lower: bool = False) -> list[str]:
        """获取日志行列表（延迟计算，独占缓存）。
        
        Args:
            lower: 是否返回小写版本的行列表
            
        Note:
            此方法与 get_lower() 互斥，调用会清除另一种格式的缓存。
            对于大文件，建议使用 iter_lines() 流式访问。
        """
        target_type = self.CACHE_LINES if not lower else self.CACHE_LOWER
        
        if self._cache_type != target_type or self._cache_lines is None:
            # 清除其他格式的缓存
            if lower:
                self._cache_lines = None


                self._cache_lower = self._crash_log.lower()
                self._cache_type = self.CACHE_LOWER
                # 对于 lower lines，从已缓存的 lower 文本分割
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
        """流式迭代日志行，不占用额外内存。
        
        适用于大文件场景，避免一次性创建完整行列表。
        """
        source = self._crash_log.lower() if lower else self._crash_log
        for line in source.splitlines():
            yield line

    def get_memory_usage(self) -> dict[str, int | bool | str]:
        """返回当前内存使用情况（用于调试/监控）。"""
        log_size = len(self._crash_log)
        cache_size = 0
        if self._cache_lower:
            cache_size += len(self._cache_lower)
        if self._cache_lines:
            # 行列表内存估算（近似）
            cache_size += sum(len(line) for line in self._cache_lines[:100])  # 采样估算
        
        return {
            "log_size_bytes": log_size,
            "cache_size_bytes": cache_size,
            "total_estimate_bytes": log_size + cache_size,
            "is_large_file": self._is_large_file,
            "cache_type": ["none", "lower", "lines"][self._cache_type]
        }

    # ---------- File I/O (Async Support) ----------

    def load_from_file_async(
        self,
        file_path: str,
        on_success: Callable[[], None],
        on_error: Callable[[Exception], None],
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> None:
        """异步加载文件内容（使用全局线程池）。"""
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
        """异步加载多个文件（使用全局线程池）。"""
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
        """同步加载单个文件。"""
        if not InputSanitizer.validate_file_path(file_path):
            raise ValueError("无效的文件路径")

        try:
            file_size = os.path.getsize(file_path)
        except OSError:
            file_size = 0

        data = ""
        if file_size > DEFAULT_MAX_BYTES:
            # 大文件：使用流式读取
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
        """同步加载多个文件并合并。"""
        combined_log: list[str] = []
        total_size = 0
        sorted_paths = sorted(set(paths))  # 去重并排序
        
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
        
        # 显示路径逻辑
        display_path = " + ".join([os.path.basename(p) for p in valid_paths[:3]])
        if len(valid_paths) > 3: 
            display_path += f" ... (+{len(valid_paths)-3} more)"
            
        self._update_state(full_data, display_path)

    def _update_state(self, content: str, path_display: str) -> None:
        """更新内部状态。"""
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
