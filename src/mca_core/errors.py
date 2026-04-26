"""
异常类和错误处理装饰器。

定义应用程序的异常层次结构，提供统一的错误处理机制。

模块说明:
    本模块提供统一的错误处理机制，包括：
        - 异常层次结构
        - 错误处理装饰器
        - 错误上下文管理器
        - 错误收集器
        - 错误报告生成
    
    主要组件:
        - AppError: 应用程序基础异常类
        - UserError: 用户可恢复错误
        - SystemError: 系统级错误
        - AnalysisError: 分析过程中的错误
        - TaskCancelledError: 任务被取消
        - ErrorHandler: 错误处理器
        - ErrorCollector: 错误收集器
"""
from __future__ import annotations

import logging
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, Generator, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AppError(Exception):
    """
    应用程序基础异常类。
    
    所有应用程序异常的基类。
    
    Attributes:
        message: 错误消息
        code: 错误代码
        details: 错误详情
        recoverable: 是否可恢复
    """
    
    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or "UNKNOWN"
        self.details = details or {}
        self.recoverable = recoverable
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "type": self.__class__.__name__,
            "message": self.message,
            "code": self.code,
            "details": self.details,
            "recoverable": self.recoverable,
            "timestamp": self.timestamp.isoformat(),
        }


class UserError(AppError):
    """用户可恢复错误（如文件格式错误、输入验证失败）。"""
    
    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, code, details, recoverable=True)


class SystemError(AppError):
    """系统级错误（如内存不足、资源不可用）。"""
    
    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, code, details, recoverable=False)


class AnalysisError(AppError):
    """分析过程中的错误。"""
    
    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        detector_name: Optional[str] = None,
    ) -> None:
        details = details or {}
        if detector_name:
            details["detector"] = detector_name
        super().__init__(message, code, details, recoverable=True)


class TaskCancelledError(AppError):
    """任务被用户或系统取消。"""
    
    def __init__(
        self,
        message: str = "Task was cancelled",
        task_id: Optional[str] = None,
    ) -> None:
        details = {"task_id": task_id} if task_id else {}
        super().__init__(message, "CANCELLED", details, recoverable=True)


class ConfigurationError(AppError):
    """配置错误。"""
    
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
    ) -> None:
        details = {"config_key": config_key} if config_key else {}
        super().__init__(message, "CONFIG_ERROR", details, recoverable=True)


class DependencyError(AppError):
    """依赖项错误。"""
    
    def __init__(
        self,
        message: str,
        dependency: Optional[str] = None,
    ) -> None:
        details = {"dependency": dependency} if dependency else {}
        super().__init__(message, "DEPENDENCY_ERROR", details, recoverable=False)


@dataclass
class ErrorRecord:
    """
    错误记录。
    
    Attributes:
        error: 异常对象
        timestamp: 时间戳
        context: 错误上下文
        traceback_str: 堆栈跟踪字符串
    """
    
    error: Exception
    timestamp: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)
    traceback_str: str = ""
    
    def __post_init__(self) -> None:
        if not self.traceback_str:
            self.traceback_str = traceback.format_exc()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        if isinstance(self.error, AppError):
            error_dict = self.error.to_dict()
        else:
            error_dict = {
                "type": self.error.__class__.__name__,
                "message": str(self.error),
            }
        
        return {
            **error_dict,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context,
            "traceback": self.traceback_str,
        }


class ErrorCollector:
    """
    错误收集器。
    
    收集多个错误，支持批量处理和报告生成。
    
    方法:
        - add: 添加错误
        - has_errors: 检查是否有错误
        - get_errors: 获取所有错误
        - clear: 清除错误
        - get_report: 生成错误报告
    
    Example:
        >>> collector = ErrorCollector()
        >>> with collector.catch("Processing file"):
        ...     process_file()
        >>> if collector.has_errors():
        ...     print(collector.get_report())
    """
    
    def __init__(self, max_errors: int = 100) -> None:
        self._errors: List[ErrorRecord] = []
        self._max_errors = max_errors
    
    def add(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        添加错误。
        
        Args:
            error: 异常对象
            context: 错误上下文
        """
        if len(self._errors) >= self._max_errors:
            self._errors.pop(0)
        
        self._errors.append(ErrorRecord(
            error=error,
            context=context or {},
        ))
    
    @contextmanager
    def catch(
        self,
        context: Optional[str] = None,
        reraise: bool = False,
    ) -> Generator[None, None, None]:
        """
        上下文管理器，自动捕获异常。
        
        Args:
            context: 上下文描述
            reraise: 是否重新抛出异常
            
        Yields:
            None
        """
        try:
            yield
        except Exception as e:
            ctx = {"context": context} if context else {}
            self.add(e, ctx)
            logger.error("Error caught: %s", e, exc_info=True)
            if reraise:
                raise
    
    def has_errors(self) -> bool:
        """检查是否有错误。"""
        return len(self._errors) > 0
    
    def get_errors(self) -> List[ErrorRecord]:
        """获取所有错误。"""
        return list(self._errors)
    
    def clear(self) -> None:
        """清除所有错误。"""
        self._errors.clear()
    
    def get_report(self) -> str:
        """
        生成错误报告。
        
        Returns:
            错误报告字符串
        """
        if not self._errors:
            return "No errors recorded."
        
        lines = [f"Error Report ({len(self._errors)} errors):", "=" * 50]
        
        for i, record in enumerate(self._errors, 1):
            error_dict = record.to_dict()
            lines.append(f"\n{i}. {error_dict.get('type', 'Unknown')}: {error_dict.get('message', 'No message')}")
            if record.context:
                lines.append(f"   Context: {record.context}")
            if record.traceback_str and not isinstance(record.error, (UserError, TaskCancelledError)):
                lines.append(f"   Traceback:\n{record.traceback_str}")
        
        return "\n".join(lines)
    
    def get_summary(self) -> Dict[str, Any]:
        """
        获取错误摘要。
        
        Returns:
            错误摘要字典
        """
        error_types: Dict[str, int] = {}
        for record in self._errors:
            error_type = record.error.__class__.__name__
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        return {
            "total_errors": len(self._errors),
            "error_types": error_types,
            "first_error": self._errors[0].timestamp.isoformat() if self._errors else None,
            "last_error": self._errors[-1].timestamp.isoformat() if self._errors else None,
        }


def error_handler(func: Callable[..., T]) -> Callable[..., T]:
    """
    装饰器：统一处理错误并转换为 AppError。

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


def safe_call(
    func: Callable[..., T],
    *args: Any,
    default: Optional[T] = None,
    **kwargs: Any,
) -> Optional[T]:
    """
    安全调用函数，捕获所有异常。

    Args:
        func: 要调用的函数
        *args: 位置参数
        default: 发生异常时的默认返回值
        **kwargs: 关键字参数

    Returns:
        函数返回值或默认值
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.warning("safe_call caught exception: %s", e)
        return default


@contextmanager
def error_context(
    context_name: str,
    reraise: bool = True,
    **extra: Any,
) -> Generator[None, None, None]:
    """
    错误上下文管理器。

    Args:
        context_name: 上下文名称
        reraise: 是否重新抛出异常
        **extra: 额外的上下文信息

    Yields:
        None

    Example:
        >>> with error_context("Loading file", file_path="/path/to/file"):
        ...     load_file()
    """
    try:
        yield
    except AppError as e:
        logger.error("[%s] %s: %s", context_name, e.code, e.message)
        if reraise:
            raise
    except Exception as e:
        logger.error("[%s] Unexpected error: %s", context_name, e, exc_info=True)
        if reraise:
            raise AnalysisError(f"{context_name}: {e}") from e
