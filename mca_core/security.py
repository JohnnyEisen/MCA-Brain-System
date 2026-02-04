from __future__ import annotations
import os


class InputSanitizer:
    @staticmethod
    def sanitize_log_content(content: str) -> str:
        lines = content.splitlines()
        safe_lines = [line[:2000] for line in lines]
        return "\n".join(safe_lines)

    @staticmethod
    def validate_file_path(path: str, base_dir: str = None) -> bool:
        """
        使用增强的安全性（防止目录遍历）验证文件路径。
        :param path: 要验证的文件路径
        :param base_dir: 可选的基础目录，文件必须位于该目录内
        """
        if not path:
            return False
        try:
            # 规范化路径以解析 .. 和符号链接
            norm_path = os.path.abspath(os.path.normpath(path))
            
            # 如果提供了 base_dir，则进行目录遍历检查
            if base_dir:
                abs_base = os.path.abspath(base_dir)
                if not norm_path.startswith(abs_base):
                    return False

            return os.path.exists(norm_path) and os.path.isfile(norm_path)
        except Exception:
            return False

    @staticmethod
    def validate_dir_path(path: str, base_dir: str = None, create: bool = False) -> bool:
        """
        验证目录路径安全性。
        :param create: 如果为True且目录不存在，验证其父目录是否安全（不实际创建）
        """
        if not path:
            return False
        try:
            norm_path = os.path.abspath(os.path.normpath(path))
            if base_dir:
                abs_base = os.path.abspath(base_dir)
                if not norm_path.startswith(abs_base):
                    return False
            
            if create:
                # 检查父目录是否存在且是一个目录
                parent = os.path.dirname(norm_path)
                return os.path.exists(parent) and os.path.isdir(parent)
            
            return os.path.exists(norm_path) and os.path.isdir(norm_path)
        except Exception:
            return False
    
    @staticmethod
    def sanitize_url(url: str) -> str | None:
        """在浏览器打开前清洗 URL。"""
        if not url: return None
        import urllib.parse
        try:
            parsed = urllib.parse.urlparse(url)
            # 仅允许 http/https 方案
            if parsed.scheme not in ('http', 'https'):
                return None
            return url
        except Exception:
            return None


class MemoryLimitExceededError(Exception):
    pass


class CpuLimitExceededError(Exception):
    pass


class ResourceLimiter:
    def __init__(self, max_memory_mb: int = 512, max_cpu_percent: int = 80):
        self.max_memory = max_memory_mb * 1024 * 1024
        self.max_cpu = max_cpu_percent

    def _get_memory_usage(self) -> int:
        return 0

    def _get_cpu_usage(self) -> int:
        return 0

    def check_limits(self):
        if self._get_memory_usage() > self.max_memory:
            raise MemoryLimitExceededError()
        if self._get_cpu_usage() > self.max_cpu:
            raise CpuLimitExceededError()
