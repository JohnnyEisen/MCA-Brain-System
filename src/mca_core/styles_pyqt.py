"""
MCA Brain System - PyQt6 样式模块

提供配色方案定义和 CSS 样式生成功能。
"""

from __future__ import annotations

from typing import Optional


class ColorPalette:
    """
    配色方案类，定义多种 UI 主题。
    
    Attributes:
        OCEAN_BLUE: 海洋蓝主题 - 专业科技感
        MINT_FRESH: 薄荷绿主题 - 清新自然
        TWILIGHT_PURPLE: 暮光紫主题 - 优雅神秘
        CORAL_PINK: 珊瑚粉主题 - 温暖活力
        DARK_SPACE: 深空灰主题 - 暗色主题
        CURRENT: 当前使用的配色方案
    """
    
    OCEAN_BLUE: dict[str, str] = {
        "bg": "#e8f0f8",
        "card_bg": "#e8f0f8",
        "shadow_light": "#ffffff",
        "shadow_dark": "#c5cdd8",
        "text_primary": "#1a365d",
        "text_secondary": "#4a5568",
        "text_muted": "#718096",
        "accent": "#3182ce",
        "accent_hover": "#2c5aa0",
        "accent_light": "#63b3ed",
        "success": "#38a169",
        "warning": "#d69e2e",
        "error": "#e53e3e",
        "info": "#3182ce",
        "border": "#cbd5e0",
        "input_bg": "#e2e8f0",
    }

    MINT_FRESH: dict[str, str] = {
        "bg": "#f0f7f4",
        "card_bg": "#f0f7f4",
        "shadow_light": "#ffffff",
        "shadow_dark": "#c8d9d1",
        "text_primary": "#1c4532",
        "text_secondary": "#2d3748",
        "text_muted": "#718096",
        "accent": "#38a169",
        "accent_hover": "#2f855a",
        "accent_light": "#68d391",
        "success": "#38a169",
        "warning": "#d69e2e",
        "error": "#e53e3e",
        "info": "#3182ce",
        "border": "#c6f6d5",
        "input_bg": "#e2e8f0",
    }

    TWILIGHT_PURPLE: dict[str, str] = {
        "bg": "#f5f3ff",
        "card_bg": "#f5f3ff",
        "shadow_light": "#ffffff",
        "shadow_dark": "#d6cfe8",
        "text_primary": "#2d3748",
        "text_secondary": "#4a5568",
        "text_muted": "#718096",
        "accent": "#805ad5",
        "accent_hover": "#6b46c1",
        "accent_light": "#b794f4",
        "success": "#38a169",
        "warning": "#d69e2e",
        "error": "#e53e3e",
        "info": "#3182ce",
        "border": "#e9d8fd",
        "input_bg": "#ede9fe",
    }

    CORAL_PINK: dict[str, str] = {
        "bg": "#fff5f5",
        "card_bg": "#fff5f5",
        "shadow_light": "#ffffff",
        "shadow_dark": "#f0d5d5",
        "text_primary": "#742a2a",
        "text_secondary": "#2d3748",
        "text_muted": "#718096",
        "accent": "#ed8936",
        "accent_hover": "#dd6b20",
        "accent_light": "#fbd38d",
        "success": "#38a169",
        "warning": "#d69e2e",
        "error": "#e53e3e",
        "info": "#3182ce",
        "border": "#fed7d7",
        "input_bg": "#fff5f5",
    }

    DARK_SPACE: dict[str, str] = {
        "bg": "#1a202c",
        "card_bg": "#2d3748",
        "shadow_light": "#4a5568",
        "shadow_dark": "#0d1117",
        "text_primary": "#f7fafc",
        "text_secondary": "#e2e8f0",
        "text_muted": "#a0aec0",
        "accent": "#63b3ed",
        "accent_hover": "#4299e1",
        "accent_light": "#90cdf4",
        "success": "#68d391",
        "warning": "#f6e05e",
        "error": "#fc8181",
        "info": "#63b3ed",
        "border": "#4a5568",
        "input_bg": "#1a202c",
    }

    CURRENT: dict[str, str] = OCEAN_BLUE


def _adjust_brightness(hex_color: str, percent: int) -> str:
    """
    调整十六进制颜色亮度。
    
    Args:
        hex_color: 十六进制颜色字符串 (如 '#FF5733')
        percent: 亮度调整百分比 (-100 到 100)
        
    Returns:
        调整后的十六进制颜色字符串
    """
    if not hex_color.startswith('#') or len(hex_color) != 7:
        return hex_color
    
    try:
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        
        r = max(0, min(255, r + int(255 * percent / 100)))
        g = max(0, min(255, g + int(255 * percent / 100)))
        b = max(0, min(255, b + int(255 * percent / 100)))
        
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_color


def _hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    """
    将十六进制颜色转换为 RGBA 格式。
    
    Args:
        hex_color: 十六进制颜色字符串
        alpha: 透明度 (0.0 - 1.0)
        
    Returns:
        RGBA 颜色字符串
    """
    if not hex_color.startswith('#') or len(hex_color) != 7:
        return f"rgba(128, 128, 128, {alpha})"
    
    try:
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        return f"rgba({r}, {g}, {b}, {alpha})"
    except Exception:
        return f"rgba(128, 128, 128, {alpha})"


def generate_silicone_css(palette: Optional[dict[str, str]] = None) -> str:
    """
    根据配色方案生成完整的 CSS 样式表。
    
    Args:
        palette: 配色方案字典，如果为 None 则使用当前配色
        
    Returns:
        完整的 CSS 样式字符串
    """
    if palette is None:
        palette = ColorPalette.CURRENT

    return f"""
/* ============================================================
   MCA 智脑系统 - 现代化玻璃拟态 UI 样式表
   设计风格: Glassmorphism + Gradient + Micro-interactions
   ============================================================ */

/* Global Font & Reset */
* {{
    font-family: 'Segoe UI', 'Microsoft YaHei', 'PingFang SC', system-ui, -apple-system, sans-serif;
    font-size: 13px;
    color: {palette['text_secondary']};
}}

/* Main Window Background with Subtle Gradient */
QMainWindow, QWidget#mainContainer {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {palette['bg']},
        stop:0.5 {_adjust_brightness(palette['bg'], 5)},
        stop:1 {_adjust_brightness(palette['bg'], 10)});
}}

/* Glass Morphism Card Frame */
QFrame#siliconeCard {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(255, 255, 255, 0.95),
        stop:1 rgba(255, 255, 255, 0.85));
    border-radius: 20px;
    border: 1px solid rgba(255, 255, 255, 0.4);
}}

/* Labels with Enhanced Typography */
QLabel {{
    color: {palette['text_primary']};
    background: transparent;
}}

QLabel#titleLabel {{
    font-size: 22px;
    font-weight: bold;
    color: {palette['text_primary']};
    letter-spacing: 1px;
}}

QLabel#subtitleLabel {{
    font-size: 12px;
    color: {palette['text_muted']};
    font-style: italic;
}}

QLabel#accentLabel {{
    color: {palette['accent']};
    font-weight: 700;
    font-size: 14px;
}}

/* Animated Neumorphic Button with Gradient */
QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {palette['bg']},
        stop:1 {_adjust_brightness(palette['bg'], -8)});
    border: none;
    border-radius: 18px;
    padding: 10px 20px;
    font-weight: 600;
    font-size: 13px;
    color: {palette['text_secondary']};
}}

QPushButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {_adjust_brightness(palette['bg'], -5)},
        stop:1 {palette['bg']});
    color: {palette['text_primary']};
    border: 1px solid {palette['accent']};
}}

QPushButton:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {_adjust_brightness(palette['bg'], -15)},
        stop:1 {_adjust_brightness(palette['bg'], -5)});
    color: {palette['accent']};
}}

QPushButton:disabled {{
    color: {palette['text_muted']};
    background: {palette['input_bg']};
}}

/* Primary Gradient Button with Glow Effect */
QPushButton#accentButton, QPushButton#primaryBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {palette['accent']},
        stop:1 {palette['accent_hover']});
    color: white;
    border-radius: 18px;
    font-weight: 700;
    border: none;
}}

QPushButton#accentButton:hover, QPushButton#primaryBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {palette['accent_hover']},
        stop:1 {palette['accent']});
    border: 2px solid rgba(255, 255, 255, 0.3);
}}

/* Success Gradient Button */
QPushButton#successBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {palette['success']},
        stop:1 {_adjust_brightness(palette['success'], -15)});
    color: white;
    border-radius: 18px;
    font-weight: 700;
}}

/* Warning Gradient Button */
QPushButton#warningBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {palette['warning']},
        stop:1 {_adjust_brightness(palette['warning'], -15)});
    color: white;
    border-radius: 18px;
    font-weight: 700;
}}

/* Danger Gradient Button */
QPushButton#dangerBtn, QPushButton#errorBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {palette['error']},
        stop:1 {_adjust_brightness(palette['error'], -15)});
    color: white;
    border-radius: 18px;
    font-weight: 700;
}}

/* Small Pill Button */
QPushButton#smallBtn {{
    padding: 6px 14px;
    font-size: 11px;
    border-radius: 12px;
    font-weight: 600;
}}

/* Floating Input Fields with Glass Effect */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(255, 255, 255, 0.9),
        stop:1 rgba(255, 255, 255, 0.7));
    border: 1px solid {palette['border']};
    border-radius: 16px;
    padding: 10px 12px;
    color: {palette['text_primary']};
    selection-background-color: {palette['accent_light']};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 2px solid {palette['accent']};
    background: rgba(255, 255, 255, 0.95);
}}

QLineEdit:placeholder {{
    color: {palette['text_muted']};
    font-style: italic;
}}

/* Modern List Widget with Hover Effects */
QListWidget, QTreeWidget {{
    background: rgba(255, 255, 255, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.5);
    border-radius: 16px;
    padding: 8px;
    color: {palette['text_primary']};
}}

QListWidget::item, QTreeWidget::item {{
    padding: 8px 12px;
    border-radius: 10px;
    margin: 3px 0;
    background: rgba(255, 255, 255, 0.5);
}}

QListWidget::item:selected, QTreeWidget::item:selected {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {palette['accent']},
        stop:1 {palette['accent_light']});
    color: white;
    font-weight: 600;
}}

QListWidget::item:hover:!selected, QTreeWidget::item:hover:!selected {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(255, 255, 255, 0.9),
        stop:1 rgba(255, 255, 255, 0.7));
}}

/* Animated Progress Bar with Gradient */
QProgressBar {{
    background: rgba(255, 255, 255, 0.3);
    border-radius: 10px;
    text-align: center;
    color: {palette['text_secondary']};
    border: none;
    height: 14px;
    font-weight: 600;
}}

QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {palette['accent']},
        stop:0.25 {palette['accent_light']},
        stop:0.5 {palette['accent']},
        stop:0.75 {palette['accent_light']},
        stop:1 {palette['accent']});
    border-radius: 12px;
}}

/* Modern Slider with Gradient Handle */
QSlider::groove:horizontal {{
    border-radius: 6px;
    height: 10px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(255, 255, 255, 0.8),
        stop:1 rgba(255, 255, 255, 0.5));
}}

QSlider::handle:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {palette['accent']},
        stop:1 {palette['accent_light']});
    border-radius: 12px;
    width: 24px;
    height: 24px;
    margin: -7px 0;
}}

/* Floating ComboBox with Glass Effect */
QComboBox {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(255, 255, 255, 0.9),
        stop:1 rgba(255, 255, 255, 0.7));
    border: 1px solid {palette['border']};
    border-radius: 16px;
    padding: 10px 14px;
    color: {palette['text_primary']};
}}

QComboBox:hover {{
    border: 2px solid {palette['accent']};
}}

QComboBox::drop-down {{
    border: none;
    width: 30px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 6px solid transparent;
    border-right: 6px solid transparent;
    border-top: 8px solid {palette['accent']};
    margin-right: 12px;
}}

QComboBox QAbstractItemView {{
    background: rgba(255, 255, 255, 0.98);
    border: 1px solid {palette['border']};
    border-radius: 16px;
    selection-background-color: {palette['accent']};
}}

/* Modern SpinBox */
QSpinBox, QDoubleSpinBox {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(255, 255, 255, 0.9),
        stop:1 rgba(255, 255, 255, 0.7));
    border: 1px solid {palette['border']};
    border-radius: 12px;
    padding: 8px 12px;
    color: {palette['text_primary']};
}}

QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 2px solid {palette['accent']};
}}

/* Custom CheckBox with Gradient */
QCheckBox {{
    spacing: 12px;
    color: {palette['text_primary']};
    font-size: 14px;
}}

QCheckBox::indicator {{
    width: 22px;
    height: 22px;
    border-radius: 8px;
    border: 2px solid {palette['border']};
    background: rgba(255, 255, 255, 0.8);
}}

QCheckBox::indicator:checked {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {palette['accent']},
        stop:1 {palette['accent_light']});
    border-color: {palette['accent']};
}}

QCheckBox::indicator:hover {{
    border: 2px solid {palette['accent']};
}}

/* Modern RadioButton */
QRadioButton {{
    spacing: 12px;
    color: {palette['text_primary']};
    font-size: 14px;
}}

QRadioButton::indicator {{
    width: 22px;
    height: 22px;
    border-radius: 11px;
    border: 2px solid {palette['border']};
    background: rgba(255, 255, 255, 0.8);
}}

QRadioButton::indicator:checked {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {palette['accent']},
        stop:1 {palette['accent_light']});
    border-color: {palette['accent']};
}}

/* TabWidget with Glass Pane */
QTabWidget::pane {{
    border: none;
    background: transparent;
}}

QTabBar::tab {{
    background: rgba(255, 255, 255, 0.6);
    border-radius: 14px;
    padding: 10px 20px;
    margin-right: 6px;
    color: {palette['text_muted']};
    font-weight: 600;
    font-size: 13px;
}}

QTabBar::tab:selected {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {palette['accent']},
        stop:1 {palette['accent_light']});
    color: white;
    font-weight: 700;
}}

QTabBar::tab:hover:!selected {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(255, 255, 255, 0.9),
        stop:1 rgba(255, 255, 255, 0.7));
    color: {palette['text_primary']};
}}

/* Modern ScrollBar with Gradient */
QScrollBar:vertical {{
    background-color: transparent;
    width: 12px;
    margin: 8px 0;
}}

QScrollBar::handle:vertical {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {palette['accent_light']},
        stop:1 {palette['accent']});
    border-radius: 6px;
    min-height: 40px;
}}

QScrollBar::handle:vertical:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {palette['accent']},
        stop:1 {palette['accent_hover']});
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 12px;
    margin: 0 8px;
}}

QScrollBar::handle:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {palette['accent_light']},
        stop:1 {palette['accent']});
    border-radius: 6px;
    min-width: 40px;
}}

/* Modern Splitter with Gradient */
QSplitter::handle {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {palette['accent_light']},
        stop:1 {palette['accent']});
    border-radius: 3px;
}}

/* Glass Menu */
QMenu {{
    background: rgba(255, 255, 255, 0.95);
    border: 1px solid rgba(255, 255, 255, 0.3);
    border-radius: 16px;
    padding: 8px;
}}

QMenu::item {{
    padding: 12px 28px;
    border-radius: 10px;
    color: {palette['text_primary']};
    font-size: 14px;
}}

QMenu::item:selected {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {palette['accent']},
        stop:1 {palette['accent_light']});
    color: white;
}}

QMenu::separator {{
    height: 1px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 transparent,
        stop:0.5 {palette['border']},
        stop:1 transparent);
    margin: 8px 12px;
}}

/* ToolTip with Glass Effect */
QToolTip {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {palette['text_primary']},
        stop:1 {_adjust_brightness(palette['text_primary'], -20)});
    color: {palette['bg']};
    border-radius: 10px;
    padding: 8px 14px;
    font-size: 13px;
    border: 1px solid rgba(255, 255, 255, 0.2);
}}

/* Modern Status Bar */
QStatusBar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(255, 255, 255, 0.8),
        stop:1 rgba(255, 255, 255, 0.6));
    color: {palette['text_muted']};
    border-top: 1px solid rgba(255, 255, 255, 0.5);
    padding: 8px;
}}

/* Modern GroupBox with Gradient Title */
QGroupBox {{
    background: rgba(255, 255, 255, 0.7);
    border-radius: 16px;
    padding: 14px;
    margin-top: 12px;
    font-weight: 700;
    color: {palette['text_primary']};
    border: 1px solid rgba(255, 255, 255, 0.5);
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 5px 14px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {palette['accent']},
        stop:1 {palette['accent_light']});
    color: white;
    border-radius: 10px;
    font-size: 13px;
}}

/* Log View with Glass Effect */
QTextBrowser {{
    background: rgba(255, 255, 255, 0.8);
    border: 1px solid {palette['border']};
    border-radius: 16px;
    padding: 12px;
    color: {palette['text_primary']};
    selection-background-color: {palette['accent_light']};
}}

/* Modern Dialog */
QDialog {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {palette['bg']},
        stop:1 {_adjust_brightness(palette['bg'], 10)});
}}

/* Badge Labels with Gradient */
QLabel#badgeSuccess {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {palette['success']},
        stop:1 {_adjust_brightness(palette['success'], -10)});
    color: white;
    border-radius: 8px;
    padding: 5px 12px;
    font-size: 11px;
    font-weight: 700;
}}

QLabel#badgeWarning {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {palette['warning']},
        stop:1 {_adjust_brightness(palette['warning'], -10)});
    color: white;
    border-radius: 8px;
    padding: 5px 12px;
    font-size: 11px;
    font-weight: 700;
}}

QLabel#badgeError {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {palette['error']},
        stop:1 {_adjust_brightness(palette['error'], -10)});
    color: white;
    border-radius: 8px;
    padding: 5px 12px;
    font-size: 11px;
    font-weight: 700;
}}

QLabel#badgeInfo {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {palette['info']},
        stop:1 {_adjust_brightness(palette['info'], -10)});
    color: white;
    border-radius: 8px;
    padding: 5px 12px;
    font-size: 11px;
    font-weight: 700;
}}
"""


SILICONE_CSS: str = generate_silicone_css(ColorPalette.OCEAN_BLUE)
