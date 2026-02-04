from __future__ import annotations
from functools import wraps
from typing import Callable, TypeVar

T = TypeVar("T")


class AppError(Exception):
    """基础异常"""


class UserError(AppError):
    """用户可恢复错误（如文件格式错误）"""


class SystemError(AppError):
    """系统错误（如内存不足）"""


class AnalysisError(AppError):
    """分析过程错误"""


class TaskCancelledError(AppError):
    """任务被取消"""


def error_handler(func: Callable[..., T]) -> Callable[..., T]:
    """装饰器统一处理错误并抛出 AppError。"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AppError:
            raise
        except Exception as exc:
            raise AnalysisError(str(exc)) from exc
    return wrapper
