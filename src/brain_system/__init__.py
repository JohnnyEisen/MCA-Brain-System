"""brain_system: 简洁可扩展的大脑核心 + DLC 框架。

这个包负责：
- 核心 BrainCore（任务调度、缓存、DLC 注册、可选监控）
- DLC 基类 BrainDLC
- 类型定义（DLCManifest / BrainDLCType）

顶层脚本（如 Bain.py）只负责：定义 DLC 实现与演示入口。
"""

from .models import BrainDLCType, DLCManifest
from .dlc import BrainDLC
from .core import BrainCore

__all__ = [
    "BrainDLCType",
    "DLCManifest",
    "BrainDLC",
    "BrainCore",
]
