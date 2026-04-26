"""
MCA Brain System - PyQt6 菜单 Mixin

提供主窗口菜单栏功能。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtWidgets import QMenuBar, QMessageBox

if TYPE_CHECKING:
    from .main_window_pyqt import SiliconeCapsuleApp


class MenuMixin:
    """菜单栏功能 Mixin。"""

    def _create_menus(self: "SiliconeCapsuleApp") -> None:
        """创建菜单栏。"""
        menubar = self.menuBar()
        if menubar is None:
            return
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: transparent;
                padding: 4px;
                font-size: 14px;
            }
            QMenuBar::item {
                padding: 4px 10px;
                border-radius: 4px;
            }
            QMenuBar::item:selected {
                background-color: #e2e8f0;
            }
            QMenu {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 5px;
            }
            QMenu::item {
                padding: 5px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #edf2f7;
            }
        """)

        self._create_file_menu(menubar)
        self._create_tools_menu(menubar)
        self._create_view_menu(menubar)
        self._create_help_menu(menubar)

    def _create_file_menu(self: "SiliconeCapsuleApp", menubar: Optional[QMenuBar]) -> None:
        """创建文件菜单。"""
        if menubar is None:
            return
        file_menu = menubar.addMenu("文件(F)")
        
        action_open = QAction("打开日志文件...", self)
        action_open.setShortcut("Ctrl+O")
        action_open.triggered.connect(self.on_load_clicked)
        file_menu.addAction(action_open)

        action_import_mods = QAction("导入 Mods 列表...", self)
        action_import_mods.triggered.connect(self.import_mods)
        file_menu.addAction(action_import_mods)
        
        action_clear = QAction("清除日志", self)
        action_clear.triggered.connect(self.clear_content)
        file_menu.addAction(action_clear)
        
        file_menu.addSeparator()
        
        action_exit = QAction("退出", self)
        action_exit.setShortcut("Ctrl+Q")
        action_exit.triggered.connect(self.close)
        file_menu.addAction(action_exit)

    def _create_tools_menu(self: "SiliconeCapsuleApp", menubar: Optional[QMenuBar]) -> None:
        """创建工具菜单。"""
        if menubar is None:
            return
        tools_menu = menubar.addMenu("工具(T)")
        
        action_export_report = QAction("导出分析报告", self)
        action_export_report.triggered.connect(self.export_report)
        tools_menu.addAction(action_export_report)

        action_start_ai = QAction("启动分析引擎", self)
        action_start_ai.triggered.connect(self.start_ai_init_if_needed)
        tools_menu.addAction(action_start_ai)

        action_export_deps = QAction("导出依赖关系(CSV)", self)
        action_export_deps.triggered.connect(self.export_dependencies)
        tools_menu.addAction(action_export_deps)

        action_save_graph = QAction("保存依赖图(PNG)", self)
        action_save_graph.triggered.connect(self.save_dependency_graph)
        tools_menu.addAction(action_save_graph)

        tools_menu.addSeparator()
        action_toggle_tail = QAction("开启/停止日志实时跟踪(Tail)", self)
        action_toggle_tail.triggered.connect(self.toggle_tail)
        tools_menu.addAction(action_toggle_tail)

        tools_menu.addSeparator()
        action_launch_generator = QAction("启动场景生成器(CLI)", self)
        action_launch_generator.triggered.connect(self.launch_adversarial_gen)
        tools_menu.addAction(action_launch_generator)

        action_launch_gpu_setup = QAction("GPU 环境配置向导", self)
        action_launch_gpu_setup.triggered.connect(self.launch_gpu_setup)
        tools_menu.addAction(action_launch_gpu_setup)

        tools_menu.addSeparator()
        action_auto_test = QAction("自动化测试", self)
        action_auto_test.triggered.connect(lambda: self.tabs.setCurrentIndex(4))
        tools_menu.addAction(action_auto_test)

    def _create_view_menu(self: "SiliconeCapsuleApp", menubar: Optional[QMenuBar]) -> None:
        """创建视图菜单。"""
        if menubar is None:
            return
        view_menu = menubar.addMenu("视图(V)")

        layout_group = QActionGroup(self)
        layout_group.setExclusive(True)

        layouts = ["spring", "circular", "kamada_kawai", "shell"]
        layout_names = ["弹簧布局", "环形布局", "KK布局", "Shell布局"]

        for layout_id, layout_name in zip(layouts, layout_names):
            action = QAction(layout_name, self)
            action.setCheckable(True)
            action.setChecked(layout_id == "spring")
            action.triggered.connect(lambda checked, l=layout_id: self.set_graph_layout(l))
            layout_group.addAction(action)
            view_menu.addAction(action)

        view_menu.addSeparator()

        action_filter = QAction("过滤孤立节点", self)
        action_filter.setCheckable(True)
        action_filter.triggered.connect(self.set_filter_isolated)
        view_menu.addAction(action_filter)

        view_menu.addSeparator()

        action_refresh_hw = QAction("刷新硬件分析", self)
        action_refresh_hw.triggered.connect(self.refresh_hardware_analysis)
        view_menu.addAction(action_refresh_hw)

    def _create_help_menu(self: "SiliconeCapsuleApp", menubar: Optional[QMenuBar]) -> None:
        """创建帮助菜单。"""
        if menubar is None:
            return
        help_menu = menubar.addMenu("帮助(H)")
        
        action_about = QAction("关于", self)
        action_about.triggered.connect(self.show_about)
        help_menu.addAction(action_about)
        
        action_copy_gl = QAction("复制 GL 片段", self)
        action_copy_gl.triggered.connect(self.copy_gl_snippets)
        help_menu.addAction(action_copy_gl)
