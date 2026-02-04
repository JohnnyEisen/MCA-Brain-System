from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List


class BrainDLCType(Enum):
    """DLC 类型枚举"""

    CORE = "core"
    OPTIMIZATION = "optimization"
    PROCESSOR = "processor"
    MANAGER = "manager"
    RESOLVER = "resolver"


@dataclass(frozen=True, slots=True)
class DLCManifest:
    """DLC 清单信息"""

    name: str
    version: str
    author: str
    description: str
    dlc_type: BrainDLCType
    dependencies: List[str] = field(default_factory=list)
    priority: int = 0
    enabled: bool = True
