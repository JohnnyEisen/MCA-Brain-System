"""异常类和错误处理装饰器。

定义应用程序的异常层次结构，提供统一的错误处理机制。
"""
from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class AppError(Exception):
    """应用程序基础异常类。"""


class UserError(AppError):
    """用户可恢复错误（如文件格式错误、输入验证失败）。"""


class SystemError(AppError):
    """系统级错误（如内存不足、资源不可用）。"""


class AnalysisError(AppError):
    """分析过程中的错误。"""


class TaskCancelledError(AppError):
    """任务被用户或系统取消。"""


def error_handler(func: Callable[..., T]) -> Callable[..., T]:
    """装饰器：统一处理错误并转换为 AppError。

    捕获函数内的所有异常，将非 AppError 异常转换为 AnalysisError。
    保留 AppError 及其子类的原始类型。

    Args:
        func: 要包装的函数。

    Returns:
        包装后的函数。

    Example:
        @error_handler
        def risky_operation() -> str:
            return some_function_that_might_fail()
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        try:
            return func(*args, **kwargs)
        except AppError:
            raise
        except Exception as exc:
            raise AnalysisError(str(exc)) from exc
    return wrapper
