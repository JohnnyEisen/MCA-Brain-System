"""大小解析工具模块。

提供文件大小字符串解析功能（如 '2MB', '512KB' 等）。
"""

from __future__ import annotations

# 从 tools.generate_mc_log 重新导出，保持兼容性
from tools.generate_mc_log import parse_size

__all__ = ["parse_size"]
