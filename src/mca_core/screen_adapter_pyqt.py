"""
MCA Brain System - PyQt6 屏幕适配模块

提供智能屏幕适配和窗口状态管理功能。
"""

from __future__ import annotations

from typing import Any, Optional

from PyQt6.QtCore import QRect, QSettings, QSize
from PyQt6.QtGui import QScreen
from PyQt6.QtWidgets import QApplication, QMainWindow


class ScreenAdapter:
    """
    智能屏幕适配器，提供精确的窗口尺寸和位置计算。
    
    功能特性:
        - 根据屏幕尺寸自动计算窗口大小
        - 支持物理尺寸精确适配（可选回退）
        - 多显示器支持
        - 高 DPI 缩放支持
    
    Attributes:
        MIN_WIDTH: 最小窗口宽度 (800px)
        MAX_WIDTH: 最大窗口宽度 (1400px)
        MIN_HEIGHT: 最小窗口高度 (600px)
        MAX_HEIGHT: 最大窗口高度 (900px)
        WIDTH_RATIO: 窗口宽度占屏幕比例 (66%)
        HEIGHT_RATIO: 窗口高度占屏幕比例 (75%)
        BASE_TOP_MARGIN: 基准顶部边距 (20px)
        BASE_SCREEN_DIAGONAL: 基准屏幕对角线尺寸 (14英寸)
        SETTINGS_ORG: QSettings 组织名
        SETTINGS_APP: QSettings 应用名
    """
    
    MIN_WIDTH: int = 800
    MAX_WIDTH: int = 1400
    MIN_HEIGHT: int = 600
    MAX_HEIGHT: int = 900
    WIDTH_RATIO: float = 0.66
    HEIGHT_RATIO: float = 0.75
    BASE_TOP_MARGIN: int = 20
    BASE_SCREEN_DIAGONAL: float = 14.0
    SETTINGS_ORG: str = "MCA"
    SETTINGS_APP: str = "BrainSystem"
    
    _debug_mode: bool = False
    
    @classmethod
    def set_debug_mode(cls, enabled: bool) -> None:
        """设置调试模式开关。"""
        cls._debug_mode = enabled
    
    @classmethod
    def _log(cls, message: str) -> None:
        """输出调试日志。"""
        if cls._debug_mode:
            print(f"[ScreenAdapter] {message}")
    
    @classmethod
    def calculate_window_size(cls, screen: QScreen) -> tuple[int, int]:
        """
        根据屏幕尺寸计算窗口大小。
        
        计算规则:
            - 窗口宽度 = 屏幕宽度的 66%（限制在 800-1400px）
            - 窗口高度 = 屏幕高度的 75%（限制在 600-900px）
        
        Args:
            screen: QScreen 对象
            
        Returns:
            (宽度, 高度) 元组
        """
        screen_geometry = screen.availableGeometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        
        raw_width = int(screen_width * cls.WIDTH_RATIO)
        raw_height = int(screen_height * cls.HEIGHT_RATIO)
        
        width = max(cls.MIN_WIDTH, min(cls.MAX_WIDTH, raw_width))
        height = max(cls.MIN_HEIGHT, min(cls.MAX_HEIGHT, raw_height))
        
        cls._log(f"屏幕尺寸: {screen_width}x{screen_height}")
        cls._log(f"计算窗口: {width}x{height}")
        
        return width, height
    
    @classmethod
    def calculate_top_margin(cls, screen: QScreen) -> int:
        """
        计算窗口顶部边距。
        
        计算规则:
            - ≤14寸小屏幕: 20px
            - ≥27寸大屏幕: 30px
            - 中间尺寸: 线性插值
        
        如果无法获取屏幕物理尺寸，则使用屏幕高度比例法
        （保持顶部边距占屏幕高度的 1.85%）。
        
        Args:
            screen: QScreen 对象
            
        Returns:
            顶部边距像素值
        """
        screen_diagonal_mm = cls._get_screen_diagonal_mm(screen)
        
        if screen_diagonal_mm and screen_diagonal_mm > 0:
            screen_diagonal_inch = screen_diagonal_mm / 25.4
            cls._log(f"屏幕物理尺寸: {screen_diagonal_inch:.1f} 英寸")
            
            if screen_diagonal_inch <= 14.0:
                top_margin = cls.BASE_TOP_MARGIN
            elif screen_diagonal_inch >= 27.0:
                top_margin = 30
            else:
                ratio = (screen_diagonal_inch - 14.0) / (27.0 - 14.0)
                top_margin = int(cls.BASE_TOP_MARGIN + ratio * (30 - cls.BASE_TOP_MARGIN))
        else:
            screen_geometry = screen.availableGeometry()
            screen_height = screen_geometry.height()
            top_margin = int(screen_height * 0.0185)
            top_margin = max(15, min(40, top_margin))
            cls._log(f"无法获取物理尺寸，使用比例法: {top_margin}px")
        
        cls._log(f"顶部边距: {top_margin}px")
        return top_margin
    
    @classmethod
    def calculate_window_position(
        cls,
        screen: QScreen,
        width: int,
        height: int
    ) -> tuple[int, int]:
        """
        计算窗口在屏幕上的位置。
        
        窗口水平居中，垂直方向根据顶部边距定位。
        
        Args:
            screen: QScreen 对象
            width: 窗口宽度
            height: 窗口高度
            
        Returns:
            (x坐标, y坐标) 元组
        """
        screen_geometry = screen.availableGeometry()
        screen_x = screen_geometry.x()
        screen_y = screen_geometry.y()
        screen_width = screen_geometry.width()
        
        top_margin = cls.calculate_top_margin(screen)
        
        x = screen_x + (screen_width - width) // 2
        y = screen_y + top_margin
        
        cls._log(f"窗口位置: ({x}, {y})")
        return x, y
    
    @classmethod
    def calculate_physical_adaptation(
        cls,
        screen: QScreen
    ) -> tuple[int, int, int] | None:
        """
        基于物理尺寸计算精确适配参数。
        
        目标: 在所有屏幕下，窗口顶部到屏幕顶部的物理距离保持一致。
        基准: 14寸 1080p 下的 20px（约 3.2mm）。
        
        Args:
            screen: QScreen 对象
            
        Returns:
            (宽度, 高度, 顶部边距) 元组，如果无法计算则返回 None
        """
        screen_diagonal_mm = cls._get_screen_diagonal_mm(screen)
        if not screen_diagonal_mm or screen_diagonal_mm <= 0:
            cls._log("无法获取屏幕物理尺寸，物理适配不可用")
            return None
        
        screen_geometry = screen.availableGeometry()
        screen_width_px = screen_geometry.width()
        screen_height_px = screen_geometry.height()
        
        screen_diagonal_inch = screen_diagonal_mm / 25.4
        screen_diagonal_px = (screen_width_px ** 2 + screen_height_px ** 2) ** 0.5
        
        ppi = screen_diagonal_px / screen_diagonal_inch
        cls._log(f"屏幕 PPI: {ppi:.1f}")
        
        base_ppi = 157.4
        base_top_margin_mm = 3.2
        base_width_mm = 310
        base_height_mm = 200
        
        top_margin_px = int(base_top_margin_mm / 25.4 * ppi)
        width_px = int(base_width_mm / 25.4 * ppi)
        height_px = int(base_height_mm / 25.4 * ppi)
        
        width_px = max(cls.MIN_WIDTH, min(cls.MAX_WIDTH, width_px))
        height_px = max(cls.MIN_HEIGHT, min(cls.MAX_HEIGHT, height_px))
        top_margin_px = max(15, min(50, top_margin_px))
        
        cls._log(f"物理适配: {width_px}x{height_px}, 顶部边距 {top_margin_px}px")
        return width_px, height_px, top_margin_px
    
    @classmethod
    def _get_screen_diagonal_mm(cls, screen: QScreen) -> float | None:
        """
        获取屏幕物理对角线尺寸（毫米）。
        
        Args:
            screen: QScreen 对象
            
        Returns:
            对角线尺寸（毫米），如果无法获取则返回 None
        """
        try:
            physical_size = screen.physicalSize()
            if physical_size.isValid():
                width_mm = physical_size.width()
                height_mm = physical_size.height()
                if width_mm > 0 and height_mm > 0:
                    diagonal_mm = (width_mm ** 2 + height_mm ** 2) ** 0.5
                    return diagonal_mm
        except Exception as e:
            cls._log(f"获取物理尺寸异常: {e}")
        return None
    
    @classmethod
    def get_screen_info(cls, screen: QScreen) -> dict[str, Any]:
        """
        获取屏幕详细信息。
        
        Args:
            screen: QScreen 对象
            
        Returns:
            包含屏幕信息的字典
        """
        geometry = screen.availableGeometry()
        physical_size = screen.physicalSize()
        diagonal_mm = cls._get_screen_diagonal_mm(screen)
        
        info: dict[str, Any] = {
            "name": screen.name(),
            "resolution": f"{geometry.width()}x{geometry.height()}",
            "geometry": {
                "x": geometry.x(),
                "y": geometry.y(),
                "width": geometry.width(),
                "height": geometry.height(),
            },
            "physical_size_mm": {
                "width": physical_size.width() if physical_size.isValid() else None,
                "height": physical_size.height() if physical_size.isValid() else None,
            },
            "diagonal_inch": round(diagonal_mm / 25.4, 2) if diagonal_mm else None,
            "dpi": screen.logicalDotsPerInch(),
            "device_pixel_ratio": screen.devicePixelRatio(),
            "refresh_rate": screen.refreshRate(),
            "orientation": str(screen.orientation()),
            "is_primary": screen == QApplication.primaryScreen(),
        }
        
        if diagonal_mm and diagonal_mm > 0:
            diagonal_px = (geometry.width() ** 2 + geometry.height() ** 2) ** 0.5
            diagonal_inch = diagonal_mm / 25.4
            info["calculated_ppi"] = round(diagonal_px / diagonal_inch, 1)
        else:
            info["calculated_ppi"] = None
        
        return info
    
    @classmethod
    def is_window_visible_on_screen(
        cls,
        geometry: QRect,
        screen: QScreen
    ) -> bool:
        """
        检查窗口是否在指定屏幕上可见。
        
        Args:
            geometry: 窗口几何信息
            screen: QScreen 对象
            
        Returns:
            如果窗口至少有 50% 在屏幕上则返回 True
        """
        screen_geometry = screen.availableGeometry()
        
        intersection = geometry.intersected(screen_geometry)
        if intersection.isEmpty():
            return False
        
        window_area = geometry.width() * geometry.height()
        intersection_area = intersection.width() * intersection.height()
        
        visibility_ratio = intersection_area / window_area if window_area > 0 else 0
        return visibility_ratio >= 0.5
    
    @classmethod
    def find_screen_by_name(cls, screen_name: str) -> QScreen | None:
        """
        根据名称查找屏幕。
        
        Args:
            screen_name: 屏幕名称
            
        Returns:
            QScreen 对象，如果未找到则返回 None
        """
        for screen in QApplication.screens():
            if screen.name() == screen_name:
                return screen
        return None
    
    @classmethod
    def get_window_screen(cls, window: QMainWindow) -> QScreen:
        """
        获取窗口当前所在的屏幕。
        
        Args:
            window: 主窗口对象
            
        Returns:
            QScreen 对象
        """
        window_center = window.geometry().center()
        for screen in QApplication.screens():
            if screen.geometry().contains(window_center):
                return screen
        return QApplication.primaryScreen() or QApplication.screens()[0]


class WindowStateManager:
    """
    窗口状态管理器，负责保存和恢复窗口状态。
    
    使用 QSettings 持久化窗口状态信息。
    
    Attributes:
        settings: QSettings 对象
    """
    
    KEY_GEOMETRY: str = "window/geometry"
    KEY_MAXIMIZED: str = "window/maximized"
    KEY_SCREEN_NAME: str = "window/screen_name"
    KEY_WIDTH: str = "window/width"
    KEY_HEIGHT: str = "window/height"
    KEY_X: str = "window/x"
    KEY_Y: str = "window/y"
    
    def __init__(self) -> None:
        """初始化窗口状态管理器。"""
        self.settings = QSettings(
            ScreenAdapter.SETTINGS_ORG,
            ScreenAdapter.SETTINGS_APP
        )
    
    def save_state(self, window: QMainWindow) -> None:
        """
        保存窗口状态。
        
        Args:
            window: 主窗口对象
        """
        geometry = window.geometry()
        screen = ScreenAdapter.get_window_screen(window)
        
        self.settings.setValue(self.KEY_GEOMETRY, geometry)
        self.settings.setValue(self.KEY_MAXIMIZED, window.isMaximized())
        self.settings.setValue(self.KEY_SCREEN_NAME, screen.name() if screen else "")
        self.settings.setValue(self.KEY_WIDTH, geometry.width())
        self.settings.setValue(self.KEY_HEIGHT, geometry.height())
        self.settings.setValue(self.KEY_X, geometry.x())
        self.settings.setValue(self.KEY_Y, geometry.y())
        
        self.settings.sync()
        ScreenAdapter._log(f"已保存窗口状态: {geometry.width()}x{geometry.height()} @ ({geometry.x()}, {geometry.y()})")
    
    def load_state(self) -> dict[str, Any] | None:
        """
        加载窗口状态。
        
        Returns:
            包含窗口状态的字典，如果没有保存的状态则返回 None
        """
        if not self.settings.contains(self.KEY_GEOMETRY):
            return None
        
        try:
            geometry = self.settings.value(self.KEY_GEOMETRY)
            if not isinstance(geometry, QRect):
                width = self.settings.value(self.KEY_WIDTH, type=int)
                height = self.settings.value(self.KEY_HEIGHT, type=int)
                x = self.settings.value(self.KEY_X, type=int)
                y = self.settings.value(self.KEY_Y, type=int)
                if width and height:
                    geometry = QRect(x, y, width, height)
                else:
                    return None
            
            return {
                "geometry": geometry,
                "maximized": self.settings.value(self.KEY_MAXIMIZED, type=bool) or False,
                "screen_name": self.settings.value(self.KEY_SCREEN_NAME, type=str) or "",
            }
        except Exception as e:
            ScreenAdapter._log(f"加载窗口状态失败: {e}")
            return None
    
    def clear_state(self) -> None:
        """清除保存的窗口状态。"""
        self.settings.remove(self.KEY_GEOMETRY)
        self.settings.remove(self.KEY_MAXIMIZED)
        self.settings.remove(self.KEY_SCREEN_NAME)
        self.settings.remove(self.KEY_WIDTH)
        self.settings.remove(self.KEY_HEIGHT)
        self.settings.remove(self.KEY_X)
        self.settings.remove(self.KEY_Y)
        self.settings.sync()
        ScreenAdapter._log("已清除窗口状态")
