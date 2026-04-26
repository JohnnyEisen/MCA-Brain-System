"""
服务层模块

提供应用服务层实现。

模块说明:
    本模块提供服务层的具体实现，包括：
        - LogService: 日志服务
        - ConfigService: 配置服务
        - DatabaseManager: 数据库管理
        - SystemService: 系统服务
        - AutoTestService: 自动测试服务
    
    接口定义见 interfaces.py。
"""

from .interfaces import (
    ILogService,
    IConfigService,
    IDatabaseService,
    ISystemService,
    IServiceFactory,
    ServiceLocator,
    LogLevel,
    LogEntry,
    AnalysisRecord,
    SystemInfo,
)
from .log_service import LogService
from .config_service import ConfigService
from .database import DatabaseManager
from .system_service import SystemService
from .auto_test_service import AutoTestService

__all__ = [
    "ILogService",
    "IConfigService",
    "IDatabaseService",
    "ISystemService",
    "IServiceFactory",
    "ServiceLocator",
    "LogLevel",
    "LogEntry",
    "AnalysisRecord",
    "SystemInfo",
    "LogService",
    "ConfigService",
    "DatabaseManager",
    "SystemService",
    "AutoTestService",
]
