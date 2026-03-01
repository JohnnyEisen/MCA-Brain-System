"""依赖注入容器模块。

提供简单的依赖注入容器，支持实例注册和工厂模式。
"""
from __future__ import annotations

from typing import Any, Callable


class DIContainer:
    """简单的依赖注入容器。

    支持单例实例注册和工厂模式延迟创建。
    """

    def __init__(self) -> None:
        """初始化容器。"""
        self._providers: dict[str, Callable[[], Any]] = {}
        self._instances: dict[str, Any] = {}

    def register_instance(self, key: str, instance: Any) -> None:
        """注册单例实例。

        Args:
            key: 服务标识符。
            instance: 服务实例。
        """
        self._instances[key] = instance

    def register_factory(self, key: str, factory: Callable[[], Any]) -> None:
        """注册工厂函数。

        Args:
            key: 服务标识符。
            factory: 创建服务的工厂函数。
        """
        self._providers[key] = factory

    def resolve(self, key: str) -> Any:
        """解析并获取服务实例。

        优先返回已注册的实例，其次使用工厂创建。

        Args:
            key: 服务标识符。

        Returns:
            服务实例。

        Raises:
            KeyError: 服务未注册。
        """
        if key in self._instances:
            return self._instances[key]
        if key in self._providers:
            instance = self._providers[key]()
            self._instances[key] = instance
            return instance
        raise KeyError(f"Service not registered: {key}")
