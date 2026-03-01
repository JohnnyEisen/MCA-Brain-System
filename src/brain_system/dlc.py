"""DLC（可下载内容）基类模块。

定义 DLC 插件的基类和接口约定。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .models import DLCManifest

if TYPE_CHECKING:
    from .core import BrainCore


class BrainDLC:
    """DLC 基类。

    子类约定：
    - 必须实现 get_manifest() 返回 DLC 元信息
    - 可选实现 _initialize() 进行初始化
    - 可选实现 shutdown() 进行清理
    - 可选实现 provide_computational_units() 提供计算单元

    Attributes:
        brain: 关联的 BrainCore 实例。
        manifest: DLC 清单元数据。
    """

    def __init__(self, brain: BrainCore) -> None:
        """初始化 DLC。

        Args:
            brain: BrainCore 实例。
        """
        self.brain = brain
        self.manifest = self.get_manifest()
        self._initialized: bool = False

    def get_manifest(self) -> DLCManifest:
        """获取 DLC 清单。

        Returns:
            DLC 元数据对象。

        Raises:
            NotImplementedError: 子类必须实现此方法。
        """
        raise NotImplementedError("子类必须实现 get_manifest 方法")

    def initialize(self) -> None:
        """初始化 DLC（仅调用一次）。"""
        if self._initialized:
            return
        self._initialize()
        self._initialized = True

    def _initialize(self) -> None:
        """子类实现的初始化逻辑。"""
        return

    def shutdown(self) -> None:
        """关闭 DLC，释放资源。"""
        return

    def provide_computational_units(self) -> dict[str, Any]:
        """提供的计算单元。

        Returns:
            计算单元名称到实例的映射。
        """
        return {}
