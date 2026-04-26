"""
控制器模块

提供基于组合模式的控制器架构。

模块说明:
    本模块提供控制器模式的实现，作为 Mixin 模式的替代方案。
    控制器将应用功能拆分为独立的类，通过依赖注入组合。

主要组件:
    - ControllerBase: 控制器基类
    - AnalysisController: 分析控制器
    - FileController: 文件操作控制器
    - UIController: UI 控制器
    - ControllerRegistry: 控制器注册表

使用方式:
    >>> from mca_core.controllers import AnalysisController, ControllerRegistry
    >>> 
    >>> registry = ControllerRegistry()
    >>> registry.register("analysis", AnalysisController, detector_registry=registry)
    >>> analysis = registry.get("analysis")
"""

from .app_controllers import (
    ControllerBase,
    AnalysisController,
    FileController,
    UIController,
    ControllerRegistry,
    AppContext,
)

__all__ = [
    "ControllerBase",
    "AnalysisController",
    "FileController",
    "UIController",
    "ControllerRegistry",
    "AppContext",
]
