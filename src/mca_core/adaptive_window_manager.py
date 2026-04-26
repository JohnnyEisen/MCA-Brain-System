"""
MCA Brain System - 自适应窗口管理器

提供智能窗口适配管理器，整合窗口适配功能。
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Optional

from PyQt6.QtCore import QObject, QRect, QSettings, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QScreen
from PyQt6.QtWidgets import QApplication, QMainWindow

from mca_core.window_constants import ScreenInfo, WindowConstants, WindowState
from mca_core.window_utils import (
    calculate_physical_adaptation,
    calculate_top_margin,
    calculate_window_position,
    calculate_window_size,
    find_screen_by_name,
    get_screen_info,
    get_window_screen,
    is_window_visible_on_screen,
)


class AdaptiveWindowSignals(QObject):
    """自适应窗口管理器信号"""

    state_saved = pyqtSignal()
    state_restored = pyqtSignal()
    screen_changed = pyqtSignal(int, str)
    debug_info = pyqtSignal(str)


class AdaptiveWindowManager(QObject):
    """
    智能窗口适配管理器

    提供完整的窗口自适应功能，包括:
    - 智能尺寸计算
    - 物理尺寸适配
    - 状态记忆
    - 多显示器支持
    """

    def __init__(
        self,
        window: QMainWindow,
        organization: str = "MCABrain",
        application: str = "MCAApp",
        debug_mode: bool = False
    ):
        """
        初始化窗口适配管理器

        Args:
            window: 需要管理的QMainWindow实例
            organization: 组织名称（用于QSettings）
            application: 应用名称（用于QSettings）
            debug_mode: 是否启用调试模式
        """
        super().__init__(window)

        self._window = window
        self._debug_mode = debug_mode
        self._signals = AdaptiveWindowSignals()

        self._settings = QSettings(organization, application)

        self._current_screen: Optional[QScreen] = None
        self._current_screen_info: Optional[ScreenInfo] = None

        self._last_saved_state: Optional[WindowState] = None
        self._is_restored = False

        self._detect_current_screen()

        if self._debug_mode:
            self._log_debug("AdaptiveWindowManager 初始化完成")

    @property
    def signals(self) -> AdaptiveWindowSignals:
        """获取信号对象"""
        return self._signals

    @property
    def current_screen_info(self) -> Optional[ScreenInfo]:
        """获取当前屏幕信息"""
        return self._current_screen_info

    @property
    def is_high_dpi(self) -> bool:
        """当前屏幕是否高DPI"""
        if self._current_screen_info:
            return self._current_screen_info.is_high_dpi
        return False

    def _detect_current_screen(self) -> None:
        """检测当前窗口所在的屏幕"""
        if not self._window:
            return

        self._current_screen = get_window_screen(self._window)
        self._update_screen_info()

    def _update_screen_info(self) -> None:
        """更新当前屏幕信息"""
        if not self._current_screen:
            return

        screen = self._current_screen
        geo = screen.geometry()
        avail = screen.availableGeometry()

        physical_size = screen.physicalSize()
        physical_w_mm = physical_size.width() if physical_size.width() > 0 else None
        physical_h_mm = physical_size.height() if physical_size.height() > 0 else None

        screens = QApplication.screens()
        screen_index = screens.index(screen) if screen in screens else 0

        self._current_screen_info = ScreenInfo(
            resolution_width=geo.width(),
            resolution_height=geo.height(),
            available_width=avail.width(),
            available_height=avail.height(),
            physical_width_mm=physical_w_mm,
            physical_height_mm=physical_h_mm,
            logical_dpi_x=screen.logicalDotsPerInchX(),
            logical_dpi_y=screen.logicalDotsPerInchY(),
            physical_dpi_x=screen.physicalDotsPerInchX(),
            physical_dpi_y=screen.physicalDotsPerInchY(),
            device_pixel_ratio=screen.devicePixelRatio(),
            name=screen.name(),
            index=screen_index
        )

        if self._debug_mode:
            info = self._current_screen_info
            self._log_debug(f"屏幕检测: {info.name} ({info.resolution_width}x{info.resolution_height})")
            if info.diagonal_inches:
                self._log_debug(f"  物理尺寸: {info.diagonal_inches:.1f}英寸, PPI: {info.ppi:.1f}")

    def calculate_window_size(self) -> QSize:
        """
        计算窗口大小

        Returns:
            计算后的窗口尺寸
        """
        if not self._current_screen:
            self._detect_current_screen()

        if not self._current_screen:
            return QSize(1200, 750)

        width, height = calculate_window_size(self._current_screen)

        physical_size = calculate_physical_adaptation(self._current_screen, self._debug_mode)
        if physical_size:
            phys_w, phys_h, _ = physical_size
            width = max(WindowConstants.MIN_WIDTH, min(phys_w, WindowConstants.MAX_WIDTH))
            height = max(WindowConstants.MIN_HEIGHT, min(phys_h, WindowConstants.MAX_HEIGHT))

        if self._debug_mode:
            self._log_debug(f"计算窗口尺寸: {width}x{height}")

        return QSize(width, height)

    def calculate_top_margin(self) -> int:
        """
        计算顶部边距

        Returns:
            顶部边距像素值
        """
        if not self._current_screen:
            self._detect_current_screen()

        if not self._current_screen:
            return WindowConstants.MARGIN_SMALL_SCREEN

        return calculate_top_margin(self._current_screen, self._debug_mode)

    def calculate_window_position(self, size: QSize) -> Any:
        """
        计算窗口位置（居中偏上）

        Args:
            size: 窗口尺寸

        Returns:
            窗口左上角坐标
        """
        if not self._current_screen:
            self._detect_current_screen()

        if not self._current_screen:
            from PyQt6.QtCore import QPoint
            return QPoint(100, 100)

        x, y = calculate_window_position(self._current_screen, size.width(), size.height(), self._debug_mode)
        from PyQt6.QtCore import QPoint
        return QPoint(x, y)

    def apply_default_geometry(self) -> None:
        """应用默认几何设置（智能适配）"""
        if not self._window:
            return

        size = self.calculate_window_size()
        pos = self.calculate_window_position(size)

        self._window.setMinimumSize(WindowConstants.MIN_WIDTH, WindowConstants.MIN_HEIGHT)

        if self._current_screen_info:
            max_w = self._current_screen_info.available_width - 40
            max_h = self._current_screen_info.available_height - 40
            self._window.setMaximumSize(max_w, max_h)

        self._window.resize(size)
        self._window.move(pos)

        if self._debug_mode:
            self._log_debug(f"应用默认几何: 位置({pos.x()}, {pos.y()}), 尺寸({size.width()}, {size.height()})")

    def save_window_state(self) -> bool:
        """
        保存窗口状态到QSettings

        Returns:
            是否保存成功
        """
        if not self._window:
            return False

        try:
            self._settings.beginGroup(WindowConstants.SETTINGS_GROUP)

            geometry = self._window.saveGeometry()
            self._settings.setValue(WindowConstants.KEY_GEOMETRY, geometry)

            is_maximized = self._window.isMaximized()
            self._settings.setValue(WindowConstants.KEY_MAXIMIZED, is_maximized)

            if self._current_screen_info:
                self._settings.setValue(WindowConstants.KEY_SCREEN, self._current_screen_info.index)
                self._settings.setValue(WindowConstants.KEY_SCREEN_NAME, self._current_screen_info.name)

            self._settings.endGroup()
            self._settings.sync()

            self._last_saved_state = WindowState(
                geometry=self._window.geometry(),
                is_maximized=is_maximized,
                screen_index=self._current_screen_info.index if self._current_screen_info else 0,
                screen_name=self._current_screen_info.name if self._current_screen_info else "",
                timestamp=__import__('time').time()
            )

            self._signals.state_saved.emit()

            if self._debug_mode:
                self._log_debug("窗口状态已保存")

            return True

        except Exception as e:
            if self._debug_mode:
                self._log_debug(f"保存窗口状态失败: {e}")
            return False

    def restore_window_state(self) -> bool:
        """
        从QSettings恢复窗口状态

        Returns:
            是否恢复成功
        """
        if not self._window:
            return False

        try:
            self._settings.beginGroup(WindowConstants.SETTINGS_GROUP)

            geometry_data = self._settings.value(WindowConstants.KEY_GEOMETRY)
            is_maximized = self._settings.value(WindowConstants.KEY_MAXIMIZED, False)
            saved_screen_index = self._settings.value(WindowConstants.KEY_SCREEN, 0)
            saved_screen_name = self._settings.value(WindowConstants.KEY_SCREEN_NAME, "")

            self._settings.endGroup()

            if geometry_data is None:
                if self._debug_mode:
                    self._log_debug("没有保存的窗口状态")
                return False

            if not self._is_geometry_valid(geometry_data, saved_screen_index, saved_screen_name):
                if self._debug_mode:
                    self._log_debug("保存的窗口状态在当前屏幕不可见，使用默认适配")
                return False

            self._window.restoreGeometry(geometry_data)

            if is_maximized:
                self._window.showMaximized()

            self._is_restored = True
            self._signals.state_restored.emit()

            if self._debug_mode:
                self._log_debug("窗口状态已恢复")

            return True

        except Exception as e:
            if self._debug_mode:
                self._log_debug(f"恢复窗口状态失败: {e}")
            return False

    def _is_geometry_valid(
        self,
        geometry_data: Any,
        saved_screen_index: int,
        saved_screen_name: str
    ) -> bool:
        """检查保存的几何信息是否有效"""
        screens = QApplication.screens()

        if saved_screen_index >= len(screens):
            if self._debug_mode:
                self._log_debug(f"屏幕索引 {saved_screen_index} 超出范围")
            return False

        if saved_screen_index < len(screens):
            current_screen = screens[saved_screen_index]
            if current_screen.name() != saved_screen_name:
                if self._debug_mode:
                    self._log_debug(f"屏幕名称不匹配: {saved_screen_name} vs {current_screen.name()}")
                return False

        return True

    def get_all_screens_info(self) -> list[ScreenInfo]:
        """获取所有显示器的信息"""
        screens = QApplication.screens()
        info_list = []

        for idx, screen in enumerate(screens):
            geo = screen.geometry()
            avail = screen.availableGeometry()
            physical_size = screen.physicalSize()

            info = ScreenInfo(
                resolution_width=geo.width(),
                resolution_height=geo.height(),
                available_width=avail.width(),
                available_height=avail.height(),
                physical_width_mm=physical_size.width() if physical_size.width() > 0 else None,
                physical_height_mm=physical_size.height() if physical_size.height() > 0 else None,
                logical_dpi_x=screen.logicalDotsPerInchX(),
                logical_dpi_y=screen.logicalDotsPerInchY(),
                physical_dpi_x=screen.physicalDotsPerInchX(),
                physical_dpi_y=screen.physicalDotsPerInchY(),
                device_pixel_ratio=screen.devicePixelRatio(),
                name=screen.name(),
                index=idx
            )
            info_list.append(info)

        return info_list

    def move_to_screen(self, screen_index: int) -> bool:
        """
        移动窗口到指定屏幕

        Args:
            screen_index: 目标屏幕索引

        Returns:
            是否移动成功
        """
        screens = QApplication.screens()
        if screen_index < 0 or screen_index >= len(screens):
            return False

        target_screen = screens[screen_index]
        self._current_screen = target_screen
        self._update_screen_info()

        size = self.calculate_window_size()
        pos = self.calculate_window_position(size)

        screen_geo = target_screen.geometry()
        pos.setX(pos.x() + screen_geo.x())
        pos.setY(pos.y() + screen_geo.y())

        self._window.resize(size)
        self._window.move(pos)

        self._signals.screen_changed.emit(screen_index, target_screen.name())

        if self._debug_mode:
            self._log_debug(f"窗口已移动到屏幕 {screen_index}: {target_screen.name()}")

        return True

    def reset_to_default(self) -> None:
        """重置窗口到当前屏幕的默认适配状态"""
        self._settings.beginGroup(WindowConstants.SETTINGS_GROUP)
        self._settings.remove("")
        self._settings.endGroup()
        self._settings.sync()

        self._detect_current_screen()
        self.apply_default_geometry()

        if self._debug_mode:
            self._log_debug("窗口已重置到默认状态")

    def get_current_screen_info_dict(self) -> dict:
        """
        获取当前屏幕的详细信息

        Returns:
            屏幕信息字典
        """
        self._detect_current_screen()
        if self._current_screen:
            return get_screen_info(self._current_screen)
        return {}

    def get_all_screens_summary(self) -> str:
        """获取所有屏幕的摘要信息（用于调试）"""
        screens_info = self.get_all_screens_info()
        lines = ["=" * 50, "显示器信息", "=" * 50]

        for info in screens_info:
            lines.append(f"\n屏幕 {info.index}: {info.name}")
            lines.append(f"  分辨率: {info.resolution_width}x{info.resolution_height}")
            lines.append(f"  可用区域: {info.available_width}x{info.available_height}")
            lines.append(f"  DPI: {info.logical_dpi_x:.1f}x{info.logical_dpi_y:.1f}")
            lines.append(f"  设备像素比: {info.device_pixel_ratio}")

            if info.diagonal_inches:
                lines.append(f"  物理尺寸: {info.diagonal_inches:.1f}英寸")
            if info.ppi:
                lines.append(f"  PPI: {info.ppi:.1f}")

            if self._current_screen_info and info.index == self._current_screen_info.index:
                lines.append("  [当前屏幕]")

        lines.append("=" * 50)
        return "\n".join(lines)

    def setup_window(self, restore: bool = True) -> None:
        """
        完整的窗口设置流程

        Args:
            restore: 是否尝试恢复上次状态
        """
        self._detect_current_screen()

        if restore:
            restored = self.restore_window_state()
            if not restored:
                self.apply_default_geometry()
        else:
            self.apply_default_geometry()

        if self._debug_mode:
            self._log_debug("窗口设置完成")

    def on_screen_changed(self, screen: QScreen) -> None:
        """屏幕改变事件处理"""
        self._current_screen = screen
        self._update_screen_info()

        if self._debug_mode:
            self._log_debug(f"屏幕改变事件: {screen.name()}")

    def _log_debug(self, message: str) -> None:
        """输出调试信息"""
        formatted = f"[AdaptiveWindow] {message}"
        print(formatted)
        self._signals.debug_info.emit(formatted)

    def set_debug_mode(self, enabled: bool) -> None:
        """设置调试模式"""
        self._debug_mode = enabled


def setup_adaptive_window(
    window: QMainWindow,
    organization: str = "MCABrain",
    application: str = "MCAApp",
    restore_state: bool = True,
    debug_mode: bool = False
) -> AdaptiveWindowManager:
    """
    便捷函数：快速设置自适应窗口

    Args:
        window: 需要设置的窗口
        organization: 组织名称
        application: 应用名称
        restore_state: 是否恢复上次状态
        debug_mode: 是否启用调试模式

    Returns:
        配置好的AdaptiveWindowManager实例
    """
    manager = AdaptiveWindowManager(
        window=window,
        organization=organization,
        application=application,
        debug_mode=debug_mode
    )
    manager.setup_window(restore=restore_state)
    return manager


def print_screen_info() -> None:
    """打印所有屏幕信息（调试用）"""
    qapp = QGuiApplication.instance()
    if not qapp:
        print("错误: 没有QApplication实例")
        return

    screens = qapp.screens()  # type: ignore[union-attr]
    print("\n" + "=" * 60)
    print("系统显示器信息")
    print("=" * 60)

    for idx, screen in enumerate(screens):
        geo = screen.geometry()
        avail = screen.availableGeometry()
        physical = screen.physicalSize()

        print(f"\n屏幕 {idx}: {screen.name()}")
        print(f"  分辨率: {geo.width()}x{geo.height()}")
        print(f"  可用区域: {avail.width()}x{avail.height()}")
        print(f"  位置: ({geo.x()}, {geo.y()})")
        print(f"  逻辑DPI: {screen.logicalDotsPerInchX():.1f}x{screen.logicalDotsPerInchY():.1f}")
        print(f"  物理DPI: {screen.physicalDotsPerInchX():.1f}x{screen.physicalDotsPerInchY():.1f}")
        print(f"  设备像素比: {screen.devicePixelRatio()}")

        if physical.width() > 0 and physical.height() > 0:
            diagonal_mm = math.sqrt(physical.width()**2 + physical.height()**2)
            diagonal_inch = diagonal_mm / 25.4
            diagonal_px = math.sqrt(geo.width()**2 + geo.height()**2)
            ppi = diagonal_px / diagonal_inch if diagonal_inch > 0 else 0

            print(f"  物理尺寸: {physical.width():.0f}x{physical.height():.0f} mm")
            print(f"  对角线: {diagonal_inch:.1f} 英寸")
            print(f"  计算PPI: {ppi:.1f}")

    print("\n" + "=" * 60)
