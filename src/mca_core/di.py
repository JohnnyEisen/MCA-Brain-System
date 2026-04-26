"""
依赖注入容器模块。

提供增强的依赖注入容器，支持：
    - 生命周期管理（单例、作用域、瞬态）
    - 工厂模式延迟创建
    - 自动注入装饰器
    - 类型安全解析
"""
from __future__ import annotations

import functools
import inspect
import logging
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Type, TypeVar, Union, get_type_hints

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ServiceLifetime(Enum):
    """服务生命周期枚举。"""
    
    SINGLETON = auto()
    SCOPED = auto()
    TRANSIENT = auto()


class ServiceDescriptor:
    """服务描述符，存储服务注册信息。"""
    
    def __init__(
        self,
        service_type: Union[Type[Any], str],
        implementation: Optional[Type[Any]] = None,
        factory: Optional[Callable[[], Any]] = None,
        instance: Optional[Any] = None,
        lifetime: ServiceLifetime = ServiceLifetime.SINGLETON,
    ) -> None:
        self.service_type = service_type
        self.implementation = implementation or (service_type if isinstance(service_type, type) else None)
        self.factory = factory
        self.instance = instance
        self.lifetime = lifetime


class DIContainer:
    """
    增强的依赖注入容器。

    支持以下功能：
        - 单例、作用域、瞬态三种生命周期
        - 工厂模式延迟创建
        - 自动注入装饰器
        - 类型安全解析
        - 依赖链检测（防止循环依赖）

    Attributes:
        _services: 服务描述符字典
        _singletons: 单例实例缓存
        _scoped_instances: 作用域实例缓存
        _resolving: 正在解析的类型集合（用于检测循环依赖）

    方法：
        - register_singleton: 注册单例服务
        - register_scoped: 注册作用域服务
        - register_transient: 注册瞬态服务
        - register_instance: 注册已存在的实例
        - register_factory: 注册工厂函数
        - resolve: 解析并获取服务实例
        - resolve_optional: 可选解析（失败返回 None）
        - inject: 自动注入装饰器
        - create_scope: 创建新的作用域
        - has: 检查服务是否已注册

    Example:
        >>> container = DIContainer()
        >>> container.register_singleton(LogService)
        >>> container.register_transient(AnalysisController)
        >>> log_service = container.resolve(LogService)
    """

    def __init__(self) -> None:
        """初始化容器。"""
        self._services: Dict[Union[Type[Any], str], ServiceDescriptor] = {}
        self._singletons: Dict[Union[Type[Any], str], Any] = {}
        self._scoped_instances: Dict[Type[Any], Any] = {}
        self._resolving: Set[Type[Any]] = set()
        self._parent: Optional["DIContainer"] = None

    def register_singleton(
        self,
        service_type: Type[T],
        implementation: Optional[Type[T]] = None,
    ) -> "DIContainer":
        """
        注册单例服务。

        整个应用程序生命周期内只创建一个实例。

        Args:
            service_type: 服务类型（通常是接口或基类）
            implementation: 实现类型（可选，默认与 service_type 相同）

        Returns:
            容器实例（支持链式调用）
        """
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            implementation=implementation,
            lifetime=ServiceLifetime.SINGLETON,
        )
        return self

    def register_scoped(
        self,
        service_type: Type[T],
        implementation: Optional[Type[T]] = None,
    ) -> "DIContainer":
        """
        注册作用域服务。

        在同一作用域内只创建一个实例。

        Args:
            service_type: 服务类型
            implementation: 实现类型（可选）

        Returns:
            容器实例（支持链式调用）
        """
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            implementation=implementation,
            lifetime=ServiceLifetime.SCOPED,
        )
        return self

    def register_transient(
        self,
        service_type: Type[T],
        implementation: Optional[Type[T]] = None,
    ) -> "DIContainer":
        """
        注册瞬态服务。

        每次请求都创建新实例。

        Args:
            service_type: 服务类型
            implementation: 实现类型（可选）

        Returns:
            容器实例（支持链式调用）
        """
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            implementation=implementation,
            lifetime=ServiceLifetime.TRANSIENT,
        )
        return self

    def register_instance(
        self,
        service_type: Union[Type[T], str],
        instance: T,
    ) -> "DIContainer":
        """
        注册已存在的实例。

        Args:
            service_type: 服务类型或字符串键
            instance: 服务实例

        Returns:
            容器实例（支持链式调用）
        """
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            instance=instance,
            lifetime=ServiceLifetime.SINGLETON,
        )
        self._singletons[service_type] = instance
        return self

    def register_factory(
        self,
        service_type: Type[T],
        factory: Callable[[], T],
        lifetime: ServiceLifetime = ServiceLifetime.SINGLETON,
    ) -> "DIContainer":
        """
        注册工厂函数。

        Args:
            service_type: 服务类型
            factory: 创建服务的工厂函数
            lifetime: 生命周期（默认单例）

        Returns:
            容器实例（支持链式调用）
        """
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            factory=factory,
            lifetime=lifetime,
        )
        return self

    def register_instance_by_key(self, key: str, instance: Any) -> None:
        """
        通过字符串键注册实例（向后兼容）。

        Args:
            key: 服务标识符
            instance: 服务实例
        """
        self._singletons[type(instance)] = instance
        self._services[type(instance)] = ServiceDescriptor(
            service_type=type(instance),
            instance=instance,
            lifetime=ServiceLifetime.SINGLETON,
        )

    def register_factory_by_key(self, key: str, factory: Callable[[], Any]) -> None:
        """
        通过字符串键注册工厂（向后兼容）。

        Args:
            key: 服务标识符
            factory: 创建服务的工厂函数
        """
        self._services[key] = ServiceDescriptor(
            service_type=key,
            factory=factory,
            lifetime=ServiceLifetime.SINGLETON,
        )

    def resolve(self, service_type: Type[T]) -> T:
        """
        解析并获取服务实例。

        Args:
            service_type: 服务类型

        Returns:
            服务实例

        Raises:
            KeyError: 服务未注册
            RuntimeError: 检测到循环依赖
        """
        if service_type not in self._services:
            raise KeyError(f"Service not registered: {service_type.__name__}")

        descriptor = self._services[service_type]

        if descriptor.instance is not None:
            return descriptor.instance

        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            if service_type in self._singletons:
                return self._singletons[service_type]

        if descriptor.lifetime == ServiceLifetime.SCOPED:
            if service_type in self._scoped_instances:
                return self._scoped_instances[service_type]

        if service_type in self._resolving:
            raise RuntimeError(
                f"Circular dependency detected: {service_type.__name__} "
                f"is already being resolved"
            )

        self._resolving.add(service_type)
        try:
            instance = self._create_instance(descriptor)

            if descriptor.lifetime == ServiceLifetime.SINGLETON:
                self._singletons[service_type] = instance
            elif descriptor.lifetime == ServiceLifetime.SCOPED:
                self._scoped_instances[service_type] = instance

            return instance
        finally:
            self._resolving.discard(service_type)

    def resolve_by_key(self, key: str) -> Any:
        """
        通过字符串键解析服务（向后兼容）。

        Args:
            key: 服务标识符

        Returns:
            服务实例
        """
        if key in self._singletons:
            return self._singletons[key]

        if key in self._services:
            descriptor = self._services[key]
            if descriptor.factory:
                instance = descriptor.factory()
                if descriptor.lifetime == ServiceLifetime.SINGLETON:
                    self._singletons[key] = instance
                return instance

        raise KeyError(f"Service not registered: {key}")

    def resolve_optional(self, service_type: Type[T]) -> Optional[T]:
        """
        可选解析服务。

        Args:
            service_type: 服务类型

        Returns:
            服务实例，如果未注册则返回 None
        """
        try:
            return self.resolve(service_type)
        except KeyError:
            return None

    def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """创建服务实例。"""
        if descriptor.factory:
            return descriptor.factory()

        impl = descriptor.implementation
        if impl is None:
            raise ValueError(f"No implementation for {descriptor.service_type}")

        try:
            hints = get_type_hints(impl.__init__)
        except Exception:
            hints = {}

        dependencies: Dict[str, Any] = {}
        sig = inspect.signature(impl.__init__)

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            if param_name in hints and param.annotation != inspect.Parameter.empty:
                dep_type = hints[param_name]
                if isinstance(dep_type, type) and dep_type in self._services:
                    dependencies[param_name] = self.resolve(dep_type)
                elif param.default != inspect.Parameter.empty:
                    dependencies[param_name] = param.default
            elif param.default != inspect.Parameter.empty:
                dependencies[param_name] = param.default

        return impl(**dependencies)

    def inject(self, func: Callable[..., T]) -> Callable[..., T]:
        """
        自动注入装饰器。

        自动解析函数参数并注入依赖。

        Args:
            func: 要装饰的函数

        Returns:
            装饰后的函数

        Example:
            >>> @container.inject
            ... def my_handler(log_service: LogService, config: ConfigService):
            ...     log_service.info(config.get("key"))
        """
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                hints = get_type_hints(func)
            except Exception:
                hints = {}

            sig = inspect.signature(func)
            bound_args = sig.bind_partial(*args, **kwargs)
            bound_args.apply_defaults()

            injected_kwargs: Dict[str, Any] = dict(bound_args.arguments)

            for param_name, param in sig.parameters.items():
                if param_name in injected_kwargs:
                    continue

                if param_name in hints:
                    dep_type = hints[param_name]
                    if isinstance(dep_type, type) and dep_type in self._services:
                        injected_kwargs[param_name] = self.resolve(dep_type)

            return func(**injected_kwargs)

        return wrapper

    def create_scope(self) -> "DIContainer":
        """
        创建新的作用域容器。

        新容器共享单例，但有独立的作用域实例。

        Returns:
            新的作用域容器
        """
        scope = DIContainer()
        scope._services = self._services
        scope._singletons = self._singletons
        scope._parent = self
        return scope

    def has(self, service_type: Type[Any]) -> bool:
        """
        检查服务是否已注册。

        Args:
            service_type: 服务类型

        Returns:
            如果已注册返回 True
        """
        return service_type in self._services

    def has_key(self, key: str) -> bool:
        """
        检查字符串键是否已注册（向后兼容）。

        Args:
            key: 服务标识符

        Returns:
            如果已注册返回 True
        """
        return key in self._singletons or key in self._services

    def clear(self) -> None:
        """清空容器（仅用于测试）。"""
        self._services.clear()
        self._singletons.clear()
        self._scoped_instances.clear()
        self._resolving.clear()

    def get_registered_services(self) -> List[Union[Type[Any], str]]:
        """
        获取所有已注册的服务类型。

        Returns:
            服务类型列表（可能包含类型或字符串键）
        """
        return list(self._services.keys())
