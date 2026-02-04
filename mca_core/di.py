from __future__ import annotations
from typing import Any, Callable, Dict


class DIContainer:
    def __init__(self) -> None:
        self._providers: Dict[str, Callable[[], Any]] = {}
        self._instances: Dict[str, Any] = {}

    def register_instance(self, key: str, instance: Any) -> None:
        self._instances[key] = instance

    def register_factory(self, key: str, factory: Callable[[], Any]) -> None:
        self._providers[key] = factory

    def resolve(self, key: str) -> Any:
        if key in self._instances:
            return self._instances[key]
        if key in self._providers:
            instance = self._providers[key]()
            self._instances[key] = instance
            return instance
        raise KeyError(f"Service not registered: {key}")
