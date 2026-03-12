"""文件操作模块（向后兼容层）。

此模块重导出 file_io 中的功能，保持向后兼容。
新代码应直接从 mca_core.file_io 导入。
"""
from __future__ import annotations

# 重导出统一的功能
from .file_io import SafeFileOperator, read_with_backup, write_atomic

__all__ = [
    "SafeFileOperator",
    "read_with_backup",
    "write_atomic",
]
