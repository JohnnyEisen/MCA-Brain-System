"""
MCA Brain System - PyQt6 主窗口 Mixin 模块

提供主窗口功能拆分的 Mixin 类。
"""

from .menu_mixin import MenuMixin
from .auto_test_mixin import AutoTestMixin
from .analysis_mixin import AnalysisMixin

__all__ = [
    "MenuMixin",
    "AutoTestMixin",
    "AnalysisMixin",
]
