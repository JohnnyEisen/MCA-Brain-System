"""资源管理工具模块。

提供资源创建、错误处理和上下文管理功能。
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator, IO


def create_resource(resource_type: str, **kwargs: Any) -> Any:
    """创建指定类型的资源。

    Args:
        resource_type: 资源类型，目前支持 "file"。
        **kwargs: 资源参数，对于 file 类型需要 path 参数。

    Returns:
        创建的资源对象。

    Raises:
        ValueError: 不支持的资源类型。
    """
    if resource_type == "file":
        return open(
            kwargs["path"],
            kwargs.get("mode", "r"),
            encoding=kwargs.get("encoding", "utf-8"),
            errors=kwargs.get("errors", "ignore"),
        )
    raise ValueError(f"Unsupported resource type: {resource_type}")


def handle_resource_error(exc: Exception, resource_type: str) -> None:
    """处理资源操作错误。

    Args:
        exc: 发生的异常。
        resource_type: 资源类型。
    """
    return


def safe_cleanup(resource: IO[Any] | None) -> None:
    """安全关闭资源，忽略所有异常。

    Args:
        resource: 要关闭的资源对象。
    """
    try:
        if resource:
            resource.close()
    except Exception:
        pass


@contextmanager
def managed_resource(
    resource_type: str, **kwargs: Any
) -> Generator[Any, None, None]:
    """上下文管理器：自动管理资源的生命周期。

    Args:
        resource_type: 资源类型。
        **kwargs: 资源参数。

    Yields:
        创建的资源对象。

    Example:
        with managed_resource("file", path="data.txt") as f:
            content = f.read()
    """
    resource: Any = None
    try:
        resource = create_resource(resource_type, **kwargs)
        yield resource
    except Exception as exc:
        handle_resource_error(exc, resource_type)
        raise
    finally:
        safe_cleanup(resource)
