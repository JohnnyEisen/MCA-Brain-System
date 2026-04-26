"""
服务层抽象接口模块

定义服务层的抽象接口，支持依赖注入和测试。

模块说明:
    本模块定义了服务层的抽象接口，包括：
        - ILogService: 日志服务接口
        - IConfigService: 配置服务接口
        - IDatabaseService: 数据库服务接口
        - ISystemService: 系统服务接口
    
    这些接口允许：
        - 依赖注入
        - 模拟测试
        - 实现替换
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Protocol, TypeVar, runtime_checkable


class LogLevel(Enum):
    """日志级别枚举。"""
    
    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()


@dataclass
class LogEntry:
    """
    日志条目。
    
    Attributes:
        level: 日志级别
        message: 日志消息
        timestamp: 时间戳
        source: 来源模块
        extra: 额外数据
    """
    
    level: LogLevel
    message: str
    timestamp: datetime
    source: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


@runtime_checkable
class ILogService(Protocol):
    """
    日志服务接口。
    
    定义日志记录的标准接口。
    """
    
    def debug(self, message: str, **kwargs: Any) -> None:
        """记录调试日志。"""
        ...
    
    def info(self, message: str, **kwargs: Any) -> None:
        """记录信息日志。"""
        ...
    
    def warning(self, message: str, **kwargs: Any) -> None:
        """记录警告日志。"""
        ...
    
    def error(self, message: str, **kwargs: Any) -> None:
        """记录错误日志。"""
        ...
    
    def critical(self, message: str, **kwargs: Any) -> None:
        """记录严重错误日志。"""
        ...
    
    def get_recent_logs(self, count: int = 100) -> List[LogEntry]:
        """获取最近的日志条目。"""
        ...


@runtime_checkable
class IConfigService(Protocol):
    """
    配置服务接口。
    
    定义配置管理的标准接口。
    """
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值。"""
        ...
    
    def set(self, key: str, value: Any) -> None:
        """设置配置值。"""
        ...
    
    def has(self, key: str) -> bool:
        """检查配置是否存在。"""
        ...
    
    def save(self) -> None:
        """保存配置。"""
        ...
    
    def reload(self) -> None:
        """重新加载配置。"""
        ...


@dataclass
class AnalysisRecord:
    """
    分析记录。
    
    Attributes:
        id: 记录 ID
        file_path: 文件路径
        file_name: 文件名
        analyzed_at: 分析时间
        issues_count: 问题数量
        summary: 分析摘要
        metadata: 元数据
    """
    
    id: Optional[int] = None
    file_path: str = ""
    file_name: str = ""
    analyzed_at: Optional[datetime] = None
    issues_count: int = 0
    summary: str = ""
    metadata: Optional[Dict[str, Any]] = None


@runtime_checkable
class IDatabaseService(Protocol):
    """
    数据库服务接口。
    
    定义数据库操作的标准接口。
    """
    
    def save_analysis(self, record: AnalysisRecord) -> int:
        """保存分析记录。"""
        ...
    
    def get_analysis(self, record_id: int) -> Optional[AnalysisRecord]:
        """获取分析记录。"""
        ...
    
    def get_recent_analyses(self, limit: int = 50) -> List[AnalysisRecord]:
        """获取最近的分析记录。"""
        ...
    
    def delete_analysis(self, record_id: int) -> bool:
        """删除分析记录。"""
        ...
    
    def search_analyses(self, query: str, limit: int = 20) -> List[AnalysisRecord]:
        """搜索分析记录。"""
        ...


@dataclass
class SystemInfo:
    """
    系统信息。
    
    Attributes:
        os_name: 操作系统名称
        os_version: 操作系统版本
        python_version: Python 版本
        cpu_count: CPU 核心数
        memory_total: 总内存（字节）
        memory_available: 可用内存（字节）
        gpu_info: GPU 信息
    """
    
    os_name: str = ""
    os_version: str = ""
    python_version: str = ""
    cpu_count: int = 0
    memory_total: int = 0
    memory_available: int = 0
    gpu_info: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "os_name": self.os_name,
            "os_version": self.os_version,
            "python_version": self.python_version,
            "cpu_count": self.cpu_count,
            "memory_total_mb": self.memory_total / (1024 * 1024),
            "memory_available_mb": self.memory_available / (1024 * 1024),
            "gpu_info": self.gpu_info,
        }


@runtime_checkable
class ISystemService(Protocol):
    """
    系统服务接口。
    
    定义系统操作的标准接口。
    """
    
    def get_system_info(self) -> SystemInfo:
        """获取系统信息。"""
        ...
    
    def get_gpu_info(self) -> Dict[str, Any]:
        """获取 GPU 信息。"""
        ...
    
    def check_dependencies(self) -> Dict[str, bool]:
        """检查依赖项。"""
        ...
    
    def open_file(self, file_path: str) -> bool:
        """打开文件。"""
        ...
    
    def open_url(self, url: str) -> bool:
        """打开 URL。"""
        ...


class IServiceFactory(ABC):
    """
    服务工厂抽象基类。
    
    定义创建服务实例的标准接口。
    """
    
    @abstractmethod
    def create_log_service(self) -> ILogService:
        """创建日志服务。"""
        ...
    
    @abstractmethod
    def create_config_service(self) -> IConfigService:
        """创建配置服务。"""
        ...
    
    @abstractmethod
    def create_database_service(self) -> IDatabaseService:
        """创建数据库服务。"""
        ...
    
    @abstractmethod
    def create_system_service(self) -> ISystemService:
        """创建系统服务。"""
        ...


T = TypeVar("T")


class ServiceLocator:
    """
    服务定位器。
    
    提供全局服务访问点，支持服务注册和获取。
    
    方法:
        - register: 注册服务
        - get: 获取服务
        - has: 检查服务是否存在
        - clear: 清除所有服务
    
    Example:
        >>> ServiceLocator.register(ILogService, log_service)
        >>> log = ServiceLocator.get(ILogService)
    """
    
    _services: Dict[type, Any] = {}
    
    @classmethod
    def register(cls, service_type: type[T], instance: T) -> None:
        """
        注册服务实例。
        
        Args:
            service_type: 服务类型
            instance: 服务实例
        """
        cls._services[service_type] = instance
    
    @classmethod
    def get(cls, service_type: type[T]) -> Optional[T]:
        """
        获取服务实例。
        
        Args:
            service_type: 服务类型
            
        Returns:
            服务实例，如果不存在返回 None
        """
        return cls._services.get(service_type)
    
    @classmethod
    def has(cls, service_type: type) -> bool:
        """
        检查服务是否已注册。
        
        Args:
            service_type: 服务类型
            
        Returns:
            如果已注册返回 True
        """
        return service_type in cls._services
    
    @classmethod
    def clear(cls) -> None:
        """清除所有已注册的服务。"""
        cls._services.clear()
