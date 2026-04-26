"""
MCA Brain System - 窗口常量和数据类

提供窗口适配相关的常量定义和数据结构。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


class WindowConstants:
    """窗口适配相关常量"""

    # 尺寸限制 (像素)
    MIN_WIDTH = 800
    MIN_HEIGHT = 600
    MAX_WIDTH = 1400
    MAX_HEIGHT = 900

    # 屏幕比例系数
    WIDTH_RATIO = 0.66
    HEIGHT_RATIO = 0.75

    # 边距设置
    MARGIN_SMALL_SCREEN = 20
    MARGIN_LARGE_SCREEN = 30
    MARGIN_FALLBACK_RATIO = 0.0185

    # 屏幕尺寸边界 (英寸)
    SCREEN_SMALL_INCH = 14.0
    SCREEN_LARGE_INCH = 27.0

    # 基准设置 (14寸 1920x1080 屏幕)
    REFERENCE_SCREEN_INCH = 14.0
    REFERENCE_RESOLUTION = (1920, 1080)
    REFERENCE_MARGIN_PX = 20
    REFERENCE_MARGIN_MM = 3.2

    # DPI设置
    DEFAULT_DPI = 96.0
    HIGH_DPI_THRESHOLD = 120.0

    # 设置存储键名
    SETTINGS_GROUP = "AdaptiveWindow"
    KEY_GEOMETRY = "geometry"
    KEY_MAXIMIZED = "maximized"
    KEY_SCREEN = "screen"
    KEY_SCREEN_NAME = "screen_name"


@dataclass
class ScreenInfo:
    """屏幕信息数据类"""

    resolution_width: int
    resolution_height: int
    available_width: int
    available_height: int

    physical_width_mm: Optional[float] = None
    physical_height_mm: Optional[float] = None

    logical_dpi_x: float = 96.0
    logical_dpi_y: float = 96.0
    physical_dpi_x: float = 96.0
    physical_dpi_y: float = 96.0

    device_pixel_ratio: float = 1.0

    name: str = "Unknown"
    index: int = 0

    @property
    def diagonal_inches(self) -> Optional[float]:
        """计算屏幕对角线尺寸（英寸）"""
        if self.physical_width_mm and self.physical_height_mm:
            mm = math.sqrt(self.physical_width_mm**2 + self.physical_height_mm**2)
            return mm / 25.4
        return None

    @property
    def ppi(self) -> Optional[float]:
        """计算像素密度 (PPI)"""
        if self.physical_width_mm and self.physical_height_mm:
            diagonal_pixels = math.sqrt(self.resolution_width**2 + self.resolution_height**2)
            diagonal_inches = self.diagonal_inches
            if diagonal_inches and diagonal_inches > 0:
                return diagonal_pixels / diagonal_inches
        return None

    @property
    def is_high_dpi(self) -> bool:
        """是否高DPI屏幕"""
        return self.logical_dpi_x >= WindowConstants.HIGH_DPI_THRESHOLD

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class WindowState:
    """窗口状态数据类"""

    geometry: Any  # QRect
    is_maximized: bool = False
    screen_index: int = 0
    screen_name: str = ""
    timestamp: float = 0.0

    def is_valid(self) -> bool:
        """检查窗口状态是否有效"""
        return self.geometry.width() > 0 and self.geometry.height() > 0
