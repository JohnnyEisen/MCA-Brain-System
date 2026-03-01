"""
UI 组件模块包。

包含应用程序的所有可复用 UI 组件。
"""

from mca_core.ui.components.log_view import LogView, ResultView
from mca_core.ui.components.main_notebook import MainNotebook
from mca_core.ui.components.menu_bar import MenuBar
from mca_core.ui.components.toolbar import Toolbar
from mca_core.ui.components.brain_monitor import BrainMonitor

__all__ = [
    "LogView",
    "ResultView",
    "MainNotebook",
    "MenuBar",
    "Toolbar",
    "BrainMonitor",
]
