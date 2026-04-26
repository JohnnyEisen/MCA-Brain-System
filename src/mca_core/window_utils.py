"""
MCA Brain System - 窗口工具函数

提供窗口适配相关的辅助函数。
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

from PyQt6.QtCore import QRect, QSize
from PyQt6.QtGui import QScreen
from PyQt6.QtWidgets import QApplication

from mca_core.window_constants import WindowConstants


def calculate_window_size(screen: QScreen) -> Tuple[int, int]:
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
    
    raw_width = int(screen_width * WindowConstants.WIDTH_RATIO)
    raw_height = int(screen_height * WindowConstants.HEIGHT_RATIO)
    
    width = max(WindowConstants.MIN_WIDTH, min(WindowConstants.MAX_WIDTH, raw_width))
    height = max(WindowConstants.MIN_HEIGHT, min(WindowConstants.MAX_HEIGHT, raw_height))
    
    return width, height


def calculate_top_margin(screen: QScreen, debug: bool = False) -> int:
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
        debug: 是否输出调试信息
        
    Returns:
        顶部边距像素值
    """
    screen_diagonal_mm = _get_screen_diagonal_mm(screen)
    
    if screen_diagonal_mm and screen_diagonal_mm > 0:
        screen_diagonal_inch = screen_diagonal_mm / 25.4
        if debug:
            print(f"[WindowUtils] 屏幕物理尺寸: {screen_diagonal_inch:.1f} 英寸")
        
        if screen_diagonal_inch <= WindowConstants.SCREEN_SMALL_INCH:
            top_margin = WindowConstants.MARGIN_SMALL_SCREEN
        elif screen_diagonal_inch >= WindowConstants.SCREEN_LARGE_INCH:
            top_margin = WindowConstants.MARGIN_LARGE_SCREEN
        else:
            ratio = (screen_diagonal_inch - WindowConstants.SCREEN_SMALL_INCH) / (
                WindowConstants.SCREEN_LARGE_INCH - WindowConstants.SCREEN_SMALL_INCH
            )
            top_margin = int(
                WindowConstants.MARGIN_SMALL_SCREEN +
                ratio * (WindowConstants.MARGIN_LARGE_SCREEN - WindowConstants.MARGIN_SMALL_SCREEN)
            )
    else:
        screen_geometry = screen.availableGeometry()
        screen_height = screen_geometry.height()
        top_margin = int(screen_height * WindowConstants.MARGIN_FALLBACK_RATIO)
        top_margin = max(15, min(40, top_margin))
        if debug:
            print(f"[WindowUtils] 无法获取物理尺寸，使用比例法: {top_margin}px")
    
    if debug:
        print(f"[WindowUtils] 顶部边距: {top_margin}px")
    return top_margin


def calculate_window_position(
    screen: QScreen,
    width: int,
    height: int,
    debug: bool = False
) -> Tuple[int, int]:
    """
    计算窗口在屏幕上的位置。
    
    窗口水平居中，垂直方向根据顶部边距定位。
    
    Args:
        screen: QScreen 对象
        width: 窗口宽度
        height: 窗口高度
        debug: 是否输出调试信息
        
    Returns:
        (x坐标, y坐标) 元组
    """
    screen_geometry = screen.availableGeometry()
    screen_x = screen_geometry.x()
    screen_y = screen_geometry.y()
    screen_width = screen_geometry.width()
    
    top_margin = calculate_top_margin(screen, debug)
    
    x = screen_x + (screen_width - width) // 2
    y = screen_y + top_margin
    
    if debug:
        print(f"[WindowUtils] 窗口位置: ({x}, {y})")
    return x, y


def calculate_physical_adaptation(
    screen: QScreen,
    debug: bool = False
) -> Optional[Tuple[int, int, int]]:
    """
    基于物理尺寸计算精确适配参数。
    
    目标: 在所有屏幕下，窗口顶部到屏幕顶部的物理距离保持一致。
    基准: 14寸 1080p 下的 20px（约 3.2mm）。
    
    Args:
        screen: QScreen 对象
        debug: 是否输出调试信息
        
    Returns:
        (宽度, 高度, 顶部边距) 元组，如果无法计算则返回 None
    """
    screen_diagonal_mm = _get_screen_diagonal_mm(screen)
    if not screen_diagonal_mm or screen_diagonal_mm <= 0:
        if debug:
            print("[WindowUtils] 无法获取屏幕物理尺寸，物理适配不可用")
        return None
    
    screen_geometry = screen.availableGeometry()
    screen_width_px = screen_geometry.width()
    screen_height_px = screen_geometry.height()
    
    screen_diagonal_inch = screen_diagonal_mm / 25.4
    screen_diagonal_px = (screen_width_px ** 2 + screen_height_px ** 2) ** 0.5
    
    ppi = screen_diagonal_px / screen_diagonal_inch
    if debug:
        print(f"[WindowUtils] 屏幕 PPI: {ppi:.1f}")
    
    base_ppi = 157.4
    base_top_margin_mm = 3.2
    base_width_mm = 310
    base_height_mm = 200
    
    top_margin_px = int(base_top_margin_mm / 25.4 * ppi)
    width_px = int(base_width_mm / 25.4 * ppi)
    height_px = int(base_height_mm / 25.4 * ppi)
    
    width_px = max(WindowConstants.MIN_WIDTH, min(WindowConstants.MAX_WIDTH, width_px))
    height_px = max(WindowConstants.MIN_HEIGHT, min(WindowConstants.MAX_HEIGHT, height_px))
    top_margin_px = max(15, min(50, top_margin_px))
    
    if debug:
        print(f"[WindowUtils] 物理适配: {width_px}x{height_px}, 顶部边距 {top_margin_px}px")
    return width_px, height_px, top_margin_px


def _get_screen_diagonal_mm(screen: QScreen) -> Optional[float]:
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
    except Exception:
        pass
    return None


def get_screen_info(screen: QScreen) -> dict:
    """
    获取屏幕详细信息。
    
    Args:
        screen: QScreen 对象
        
    Returns:
        包含屏幕信息的字典
    """
    geometry = screen.availableGeometry()
    physical_size = screen.physicalSize()
    diagonal_mm = _get_screen_diagonal_mm(screen)
    
    info = {
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


def is_window_visible_on_screen(
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


def find_screen_by_name(screen_name: str) -> Optional[QScreen]:
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


def get_window_screen(window) -> Optional[QScreen]:
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
    return QApplication.primaryScreen()
