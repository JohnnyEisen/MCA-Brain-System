"""统一 UI 样式配置模块。

提供 ttk 组件的统一样式定义，确保整个应用视觉一致性。
支持明暗主题切换。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Optional


class StyleConfig:
    """样式配置类。
    
    定义所有组件的统一样式，包括：
    - 字体
    - 颜色
    - 间距
    - 组件尺寸
    """
    
    # 字体配置
    FONT_FAMILY = "Segoe UI"
    FONT_FAMILY_MONO = "Consolas"
    FONT_SIZE_NORMAL = 9
    FONT_SIZE_SMALL = 8
    FONT_SIZE_LARGE = 11
    FONT_SIZE_TITLE = 14
    
    # 颜色配置（亮色主题）
    COLORS_LIGHT = {
        "bg": "#f0f0f0",
        "fg": "#2c3e50",
        "accent": "#3498db",
        "success": "#27ae60",
        "warning": "#f39c12",
        "error": "#e74c3c",
        "muted": "#7f8c8d",
        "border": "#bdc3c7",
        "highlight": "#fff3cd",
    }
    
    # 颜色配置（暗色主题）
    COLORS_DARK = {
        "bg": "#1e1e1e",
        "fg": "#e0e0e0",
        "accent": "#5dade2",
        "success": "#58d68d",
        "warning": "#f4d03f",
        "error": "#ec7063",
        "muted": "#95a5a6",
        "border": "#3c3c3c",
        "highlight": "#3d3d00",
    }
    
    # 间距配置
    PADDING_SMALL = 4
    PADDING_NORMAL = 8
    PADDING_LARGE = 12
    
    # 按钮宽度
    BUTTON_WIDTH_SMALL = 8
    BUTTON_WIDTH_NORMAL = 12
    BUTTON_WIDTH_LARGE = 16
    
    # 输入框宽度
    ENTRY_WIDTH_SMALL = 8
    ENTRY_WIDTH_NORMAL = 20
    ENTRY_WIDTH_LARGE = 40
    
    def __init__(self, root: Optional[tk.Tk] = None, theme: str = "light") -> None:
        """初始化样式配置。
        
        Args:
            root: Tk 根窗口。
            theme: 主题名称 ("light" 或 "dark")。
        """
        self.root = root
        self.theme = theme
        self.colors = self.COLORS_LIGHT if theme == "light" else self.COLORS_DARK
        self._style: ttk.Style | None = None
        
    def apply(self) -> ttk.Style:
        """应用样式配置。
        
        Returns:
            ttk.Style 实例。
        """
        if self._style is not None:
            return self._style
            
        self._style = ttk.Style()
        
        # 尝试使用 sv_ttk 主题
        try:
            import sv_ttk
            sv_ttk.set_theme(self.theme)
        except ImportError:
            # 回退到默认主题
            self._apply_default_theme()
        
        # 自定义样式
        self._configure_custom_styles()
        
        return self._style
    
    def _apply_default_theme(self) -> None:
        """应用默认主题（无 sv_ttk 时）。"""
        if self._style is None:
            return
            
        # 使用 clam 主题作为基础
        available_themes = self._style.theme_names()
        if "clam" in available_themes:
            self._style.theme_use("clam")
        elif "vista" in available_themes:
            self._style.theme_use("vista")
    
    def _configure_custom_styles(self) -> None:
        """配置自定义样式。"""
        if self._style is None:
            return
            
        style = self._style
        colors = self.colors
        
        # 按钮样式
        style.configure(
            "Accent.TButton",
            font=(self.FONT_FAMILY, self.FONT_SIZE_NORMAL),
            padding=(self.PADDING_NORMAL, self.PADDING_SMALL),
        )
        
        style.configure(
            "Small.TButton",
            font=(self.FONT_FAMILY, self.FONT_SIZE_SMALL),
            padding=(self.PADDING_SMALL, 2),
        )
        
        # 标签样式
        style.configure(
            "Title.TLabel",
            font=(self.FONT_FAMILY, self.FONT_SIZE_TITLE, "bold"),
            foreground=colors["fg"],
        )
        
        style.configure(
            "Muted.TLabel",
            font=(self.FONT_FAMILY, self.FONT_SIZE_SMALL),
            foreground=colors["muted"],
        )
        
        style.configure(
            "Success.TLabel",
            font=(self.FONT_FAMILY, self.FONT_SIZE_NORMAL),
            foreground=colors["success"],
        )
        
        style.configure(
            "Warning.TLabel",
            font=(self.FONT_FAMILY, self.FONT_SIZE_NORMAL),
            foreground=colors["warning"],
        )
        
        style.configure(
            "Error.TLabel",
            font=(self.FONT_FAMILY, self.FONT_SIZE_NORMAL),
            foreground=colors["error"],
        )
        
        # LabelFrame 样式
        style.configure(
            "Card.TLabelframe",
            padding=self.PADDING_NORMAL,
        )
        
        style.configure(
            "Card.TLabelframe.Label",
            font=(self.FONT_FAMILY, self.FONT_SIZE_NORMAL, "bold"),
            foreground=colors["fg"],
        )
        
        # Entry 样式
        style.configure(
            "Mono.TEntry",
            font=(self.FONT_FAMILY_MONO, self.FONT_SIZE_NORMAL),
        )
        
        # 进度条样式
        style.configure(
            "Accent.Horizontal.TProgressbar",
            troughcolor=colors["border"],
            background=colors["accent"],
        )
    
    def set_theme(self, theme: str) -> None:
        """切换主题。
        
        Args:
            theme: 主题名称 ("light" 或 "dark")。
        """
        self.theme = theme
        self.colors = self.COLORS_LIGHT if theme == "light" else self.COLORS_DARK
        
        # 重新应用主题
        try:
            import sv_ttk
            sv_ttk.set_theme(theme)
        except ImportError:
            pass
        
        # 重新配置自定义样式
        self._configure_custom_styles()
    
    def get_font(self, mono: bool = False, size: Optional[int] = None, bold: bool = False) -> tuple[str, int, str]:
        """获取字体配置。
        
        Args:
            mono: 是否使用等宽字体。
            size: 字体大小，None 使用默认值。
            bold: 是否加粗。
            
        Returns:
            字体配置元组。
        """
        family = self.FONT_FAMILY_MONO if mono else self.FONT_FAMILY
        font_size = size or self.FONT_SIZE_NORMAL
        weight = "bold" if bold else "normal"
        return (family, font_size, weight)
    
    def get_color(self, name: str) -> str:
        """获取颜色值。
        
        Args:
            name: 颜色名称 (bg, fg, accent, success, warning, error, muted, border)。
            
        Returns:
            颜色值（十六进制）。
        """
        return self.colors.get(name, self.colors["fg"])


def apply_styles(root: tk.Tk, theme: str = "light") -> StyleConfig:
    """应用统一样式配置。
    
    Args:
        root: Tk 根窗口。
        theme: 主题名称 ("light" 或 "dark")。
        
    Returns:
        StyleConfig 实例。
    """
    config = StyleConfig(root, theme)
    config.apply()
    return config


# 全局样式实例（延迟初始化）
_style_config: StyleConfig | None = None


def get_style_config() -> StyleConfig:
    """获取全局样式配置实例。
    
    Returns:
        StyleConfig 实例。
    """
    global _style_config
    if _style_config is None:
        _style_config = StyleConfig()
    return _style_config
