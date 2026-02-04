from __future__ import annotations

from typing import Any, Dict

from .models import DLCManifest


class BrainDLC:
    """DLC 基类。

    约定：
    - 子类实现 get_manifest() 与 _initialize()。
    - initialize() 只会被 BrainCore 调用一次。
    """

    def __init__(self, brain: "BrainCore"):
        self.brain = brain
        self.manifest = self.get_manifest()
        self._initialized = False

    def get_manifest(self) -> DLCManifest:
        raise NotImplementedError("子类必须实现 get_manifest 方法")

    def initialize(self) -> None:
        if self._initialized:
            return
        self._initialize()
        self._initialized = True

    def _initialize(self) -> None:
        return

    def shutdown(self) -> None:
        return

    def provide_computational_units(self) -> Dict[str, Any]:
        return {}


# 避免类型检查循环引用
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .core import BrainCore
