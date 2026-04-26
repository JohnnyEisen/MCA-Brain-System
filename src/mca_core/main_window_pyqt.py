"""
MCA Brain System - PyQt6 主窗口模块

提供主应用窗口类 SiliconeCapsuleApp。
"""

from __future__ import annotations

import csv
import json
import os
import platform
import re
import sys
import threading
import time
from collections import Counter, defaultdict
from typing import TYPE_CHECKING, Any, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config.constants import CONFIG_FILE, GPU_ISSUES_FILE
from mca_core.hardware_analysis import analyze_hardware_log
from mca_core.services.config_service import ConfigService
from mca_core.diagnostic_engine import DiagnosticEngine
from mca_core.services.log_service import LogService
from mca_core.services.system_service import SystemService
from mca_core.screen_adapter_pyqt import ScreenAdapter, WindowStateManager
from mca_core.styles_pyqt import SILICONE_CSS
try:
    from mca_core.brain_animation_pyqt import BrainMonitorWidget
except Exception:
    BrainMonitorWidget = None

from mca_core.workers_pyqt import (
    AIInitWorker,
    AnalysisWorker,
    AutoTestWorker,
    HAS_BRAIN,
)
from mca_core.main_window_mixins import MenuMixin, AutoTestMixin, AnalysisMixin

if TYPE_CHECKING:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from matplotlib.figure import Figure

try:
    import networkx as nx
    HAS_NX: bool = True
except ImportError:
    HAS_NX = False
    nx = None

try:
    from brain_system.core import BrainCore
    HAS_BRAIN_CORE: bool = True
except ImportError:
    HAS_BRAIN_CORE = False
    BrainCore = None

_FigureCanvas: Optional[type] = None
_Figure: Optional[type] = None

SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR: str = os.path.dirname(os.path.dirname(SCRIPT_DIR))
HISTORY_FILE: str = os.path.join(ROOT_DIR, "data", "analysis_history.csv")

MODE_DESCRIPTIONS = [
    ("略微", "保守策略 - 适合低内存环境，减少内存占用但可能增加 CPU 消耗。"),
    ("标准", "推荐配置 - 平衡内存回收频率与分析吞吐量，适合大多数场景。"),
    ("激进", "高性能 - 减少 GC 频率，大幅提升大文件分析速度，但内存占用较高。")
]

SCENARIOS: dict[str, str] = {
    "normal": "正常日志",
    "oom": "内存溢出",
    "missing_dependency": "缺失前置",
    "gl_error": "OpenGL 错误",
    "mixin_conflict": "Mixin 冲突",
    "version_conflict": "版本冲突",
    "compound": "复合错误",
    "adversarial": "对抗样本",
}


class SiliconeCapsuleApp(MenuMixin, AutoTestMixin, AnalysisMixin, QMainWindow):
    """
    MCA 智脑系统主应用窗口。
    
    提供现代化的拟态风格 UI，用于 Minecraft 崩溃日志分析。
    
    功能特性:
        - 智能屏幕适配
        - 窗口状态记忆
        - 多显示器支持
        - 高 DPI 缩放
    
    继承自:
        MenuMixin: 菜单栏功能
        AutoTestMixin: 自动化测试功能
        AnalysisMixin: 分析功能
        QMainWindow: Qt 主窗口
    
    Attributes:
        log_service: 日志服务
        config_service: 配置服务
        engine: 诊断引擎
        brain: BrainCore AI 引擎
        graph_canvas: 图表画布
        _window_state_manager: 窗口状态管理器
        _use_physical_adaptation: 是否使用物理尺寸适配
    """
    
    tail_line_signal = pyqtSignal(str)

    def _set_brain_monitor_state(self, state: str) -> None:
        """同步大脑动画状态。"""
        monitor = getattr(self, "brain_monitor", None)
        if monitor is None:
            return
        try:
            if state == "loading":
                monitor.start_loading()
            elif state == "active":
                monitor.start_active()
            elif state == "error":
                monitor.set_status("错误")
            elif state == "idle":
                monitor.stop()
        except Exception:
            pass

    def _set_status_text(self, text: str) -> None:
        """统一更新状态栏文本，并驱动大脑动画状态。"""
        self.status_label.setText(text)

        monitor = getattr(self, "brain_monitor", None)
        if monitor is not None:
            try:
                monitor.set_status(text)
            except Exception:
                pass

    def __init__(self, use_physical_adaptation: bool = True, debug_mode: bool = False) -> None:
        """
        初始化主应用窗口。
        
        Args:
            use_physical_adaptation: 是否尝试使用物理尺寸适配，默认 True
            debug_mode: 是否启用调试模式，默认 False
        """
        ScreenAdapter.set_debug_mode(debug_mode)
        self._use_physical_adaptation = use_physical_adaptation
        self._window_state_manager = WindowStateManager()
        
        super().__init__()
        self._init_window()
        self._init_backend()
        self.setup_ui()
        self._create_menus()
        self.tail_line_signal.connect(self._append_tail_line)

    def _init_window(self) -> None:
        """
        初始化窗口配置。
        
        执行智能屏幕适配流程:
            1. 尝试恢复上次保存的窗口状态
            2. 如果没有保存状态或状态无效，执行智能适配
            3. 设置窗口大小限制
        """
        self.setWindowTitle("MCA 智脑系统 - 硅胶拟态核心控制台")
        self.setStyleSheet(SILICONE_CSS)
        
        self._set_window_icon()
        
        primary_screen = self.screen()
        if primary_screen is None:
            from PyQt6.QtWidgets import QApplication
            primary_screen = QApplication.primaryScreen()
        if primary_screen is None:
            self.resize(1200, 800)
            self.setMinimumSize(ScreenAdapter.MIN_WIDTH, ScreenAdapter.MIN_HEIGHT)
            return
        
        saved_state = self._window_state_manager.load_state()
        
        if saved_state:
            geometry = saved_state.get("geometry")
            screen_name = saved_state.get("screen_name", "")
            was_maximized = saved_state.get("maximized", False)
            
            target_screen = None
            if screen_name:
                target_screen = ScreenAdapter.find_screen_by_name(screen_name)
            
            if target_screen is None:
                target_screen = primary_screen
            
            if geometry and ScreenAdapter.is_window_visible_on_screen(geometry, target_screen):
                self.setGeometry(geometry)
                self.setMinimumSize(ScreenAdapter.MIN_WIDTH, ScreenAdapter.MIN_HEIGHT)
                
                screen_geometry = target_screen.availableGeometry()
                max_width = screen_geometry.width() - 40
                max_height = screen_geometry.height() - 40
                self.setMaximumSize(max_width, max_height)
                
                if was_maximized:
                    self.showMaximized()
                
                ScreenAdapter._log(f"已恢复窗口状态: {geometry.width()}x{geometry.height()}")
                return
            else:
                ScreenAdapter._log("保存的窗口状态无效，执行智能适配")
        
        self._apply_smart_adaptation(primary_screen)

    def _set_window_icon(self) -> None:
        """设置窗口图标。"""
        from PyQt6.QtGui import QIcon
        
        icon_paths = [
            os.path.join(ROOT_DIR, "app_icon.ico"),
            os.path.join(ROOT_DIR, "assets", "app_icon.ico"),
            os.path.join(ROOT_DIR, "resources", "app_icon.ico"),
        ]
        
        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                try:
                    self.setWindowIcon(QIcon(icon_path))
                    return
                except Exception:
                    pass
        
        from PyQt6.QtGui import QPixmap, QPainter
        from PyQt6.QtCore import Qt
        
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        from PyQt6.QtGui import QColor, QFont, QPen, QBrush
        
        painter.setBrush(QBrush(QColor("#3182ce")))
        painter.setPen(QPen(QColor("#2c5aa0"), 2))
        painter.drawEllipse(4, 4, 56, 56)
        
        painter.setPen(QPen(QColor("#ffffff")))
        font = QFont("Arial", 24, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "M")
        painter.end()
        
        self.setWindowIcon(QIcon(pixmap))

    def _apply_smart_adaptation(self, screen) -> None:
        """
        应用智能屏幕适配。
        
        优先尝试物理尺寸适配，如果失败则回退到比例适配。
        
        Args:
            screen: 目标屏幕
        """
        width: int
        height: int
        top_margin: int
        
        if self._use_physical_adaptation:
            physical_result = ScreenAdapter.calculate_physical_adaptation(screen)
            if physical_result:
                width, height, top_margin = physical_result
                ScreenAdapter._log("使用物理尺寸适配")
            else:
                width, height = ScreenAdapter.calculate_window_size(screen)
                top_margin = ScreenAdapter.calculate_top_margin(screen)
                ScreenAdapter._log("物理适配不可用，回退到比例适配")
        else:
            width, height = ScreenAdapter.calculate_window_size(screen)
            top_margin = ScreenAdapter.calculate_top_margin(screen)
            ScreenAdapter._log("使用比例适配")
        
        x, y = ScreenAdapter.calculate_window_position(screen, width, height)
        
        self.setGeometry(x, y, width, height)
        
        self.setMinimumSize(ScreenAdapter.MIN_WIDTH, ScreenAdapter.MIN_HEIGHT)
        
        screen_geometry = screen.availableGeometry()
        max_width = screen_geometry.width() - 40
        max_height = screen_geometry.height() - 40
        self.setMaximumSize(max_width, max_height)
        
        ScreenAdapter._log(f"窗口已适配: {width}x{height} @ ({x}, {y})")

    def reset_to_default(self) -> None:
        """
        重置窗口到当前屏幕的默认适配状态。
        
        清除保存的窗口状态，重新执行智能适配。
        """
        self._window_state_manager.clear_state()
        
        current_screen = ScreenAdapter.get_window_screen(self)
        if current_screen is None:
            from PyQt6.QtWidgets import QApplication
            current_screen = QApplication.primaryScreen()
        
        if current_screen:
            self._apply_smart_adaptation(current_screen)
            if self.isMaximized():
                self.showNormal()
        
        ScreenAdapter._log("窗口已重置到默认状态")

    def get_current_screen_info(self) -> dict[str, Any]:
        """
        获取当前屏幕的详细信息。
        
        Returns:
            包含屏幕信息的字典
        """
        current_screen = ScreenAdapter.get_window_screen(self)
        if current_screen is None:
            from PyQt6.QtWidgets import QApplication
            current_screen = QApplication.primaryScreen()
        
        if current_screen:
            return ScreenAdapter.get_screen_info(current_screen)
        
        return {
            "name": "Unknown",
            "resolution": "Unknown",
            "geometry": {},
            "physical_size_mm": {},
            "diagonal_inch": None,
            "dpi": 96,
            "device_pixel_ratio": 1.0,
            "refresh_rate": 60.0,
            "orientation": "Unknown",
            "is_primary": True,
            "calculated_ppi": None,
        }

    def closeEvent(self, event) -> None:
        """
        处理窗口关闭事件。
        
        保存窗口状态到 QSettings。
        
        Args:
            event: 关闭事件对象
        """
        self._window_state_manager.save_state(self)
        ScreenAdapter._log("窗口关闭，状态已保存")
        event.accept()

    def _init_backend(self) -> None:
        """初始化后端服务。"""
        self.log_service = LogService()
        self.config_service = ConfigService(CONFIG_FILE)
        data_dir = os.path.join(ROOT_DIR, "data")
        os.makedirs(data_dir, exist_ok=True)
        self.engine = DiagnosticEngine(data_dir=data_dir)
        self.file_path = ""
        self.current_dep_pairs: set[tuple[str, str]] = set()
        self.current_mods: dict[str, set] = {}
        self.current_cause_counts: dict[str, int] = {}
        self._tail_running = False
        self._tail_stop_event = threading.Event()
        self.graph_layout_name = "spring"
        self.filter_isolated_nodes = True
        self.gl_snippets: list[str] = []
        self.hardware_issues: list[str] = []
        self.auto_test_worker: Optional[AutoTestWorker] = None
        self.ai_init_worker: Optional[AIInitWorker] = None
        self.brain: Any = None
        self.graph_canvas: Any = None
        self._graph_placeholder: Optional[QLabel] = None
        self._brain_config_path: Optional[str] = None
        
        if HAS_BRAIN and HAS_BRAIN_CORE:
            try:
                brain_config = os.path.join(ROOT_DIR, "config", "brain_config.json")
                if not os.path.exists(brain_config):
                    brain_config = None
                self._brain_config_path = brain_config
                if BrainCore is not None:
                    self.brain = BrainCore(config_path=brain_config)
            except Exception as e:
                print(f"Failed to load BrainCore: {e}")

    def _ensure_graph_canvas(self) -> bool:
        """确保图表画布已初始化。"""
        if self.graph_canvas is not None:
            return True

        global _FigureCanvas, _Figure
        if _FigureCanvas is None or _Figure is None:
            try:
                from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as _FigureCanvas
                from matplotlib.figure import Figure as _Figure
                _FigureCanvas = _FigureCanvas
                _Figure = _Figure
            except Exception as e:
                QMessageBox.warning(self, "图表初始化失败", f"无法加载 Matplotlib 图形后端: {e}")
                return False

        try:
            self.graph_canvas = _FigureCanvas(_Figure(figsize=(5, 4), dpi=100))
            if self._graph_placeholder is not None:
                self.tab_graphs_layout.removeWidget(self._graph_placeholder)
                self._graph_placeholder.deleteLater()
                self._graph_placeholder = None
            self.tab_graphs_layout.addWidget(self.graph_canvas)
            return True
        except Exception as e:
            QMessageBox.warning(self, "图表初始化失败", f"创建图表控件失败: {e}")
            self.graph_canvas = None
            return False

    def _create_menus(self) -> None:
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

    def _create_file_menu(self, menubar: Optional[QMenuBar]) -> None:
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

    def _create_tools_menu(self, menubar: Optional[QMenuBar]) -> None:
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
        
        action_view_history = QAction("查看分析历史", self)
        action_view_history.triggered.connect(self.view_history)
        tools_menu.addAction(action_view_history)

    def _create_view_menu(self, menubar: Optional[QMenuBar]) -> None:
        """创建视图菜单。"""
        if menubar is None:
            return
        view_menu = menubar.addMenu("视图(V)")

        action_refresh_hardware = QAction("刷新硬件分析", self)
        action_refresh_hardware.triggered.connect(self.refresh_hardware_analysis)
        view_menu.addAction(action_refresh_hardware)

        action_copy_gl = QAction("复制 GL 片段", self)
        action_copy_gl.triggered.connect(self.copy_gl_snippets)
        view_menu.addAction(action_copy_gl)

        view_menu.addSeparator()
        layout_menu = view_menu.addMenu("依赖图布局")
        self.layout_actions: dict[str, QAction] = {}
        layout_group = QActionGroup(self)
        layout_group.setExclusive(True)
        for layout_key, label in [
            ("spring", "Spring"),
            ("circular", "Circular"),
            ("shell", "Shell"),
            ("spectral", "Spectral"),
            ("random", "Random"),
        ]:
            act = QAction(label, self)
            act.setCheckable(True)
            act.triggered.connect(lambda checked, k=layout_key: self.set_graph_layout(k))
            layout_group.addAction(act)
            layout_menu.addAction(act)
            self.layout_actions[layout_key] = act
        self.layout_actions["spring"].setChecked(True)

        action_filter_iso = QAction("过滤孤立节点", self)
        action_filter_iso.setCheckable(True)
        action_filter_iso.setChecked(True)
        action_filter_iso.triggered.connect(self.set_filter_isolated)
        view_menu.addAction(action_filter_iso)
        self.action_filter_isolated = action_filter_iso

    def _create_help_menu(self, menubar: Optional[QMenuBar]) -> None:
        """创建帮助菜单。"""
        if menubar is None:
            return
        help_menu = menubar.addMenu("帮助(H)")
        action_about = QAction("关于 MCA", self)
        action_about.triggered.connect(self.show_about)
        help_menu.addAction(action_about)

    def clear_content(self) -> None:
        """清除所有内容。"""
        self.log_text_edit.clear()
        self._set_status_text("状态: 就绪")
        self._set_brain_monitor_state("idle")
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.setText("开始智能分析")
        self.file_path = ""
        self.current_dep_pairs = set()
        self.current_mods = {}
        self.current_cause_counts = {}
        self.gl_snippets = []
        self.hardware_issues = []
        if self._tail_running:
            self._tail_stop_event.set()
            self._tail_running = False
        if self.auto_test_worker and self.auto_test_worker.isRunning():
            self.auto_test_worker.cancel()
        self.result_text_edit.clear()
        self.mod_list_widget.clear()
        if hasattr(self, "hardware_text_edit"):
            self.hardware_text_edit.clear()
        
        while self.tab_graphs_layout.count():
            item = self.tab_graphs_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.progress.setValue(0)
        self.progress.hide()

    def export_report(self) -> None:
        """导出分析报告。"""
        if not self.result_text_edit.toPlainText():
            QMessageBox.warning(self, "无内容", "当前没有分析结果可供导出。")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存分析报告",
            os.path.join(os.path.expanduser("~"), "MCA_Report.txt"),
            "Text Files (*.txt);;Markdown Files (*.md);;All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.result_text_edit.toPlainText())
                QMessageBox.information(self, "导出成功", f"报告已成功导出至：\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "导出失败", f"无法写入文件：{str(e)}")

    def export_dependencies(self) -> None:
        """导出依赖关系。"""
        if not self.current_dep_pairs:
            QMessageBox.information(self, "提示", "没有依赖数据可导出。")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存依赖关系",
            os.path.join(os.path.expanduser("~"), "mod_dependencies.csv"),
            "CSV Files (*.csv);;All Files (*)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["Source Mod", "Requires Target", "Status"])
                for src, tgt in sorted(self.current_dep_pairs):
                    status = "Present" if tgt in self.current_mods else "Missing"
                    writer.writerow([src, tgt, status])
            QMessageBox.information(self, "导出成功", f"依赖关系已导出至:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"无法导出依赖关系: {e}")

    def save_dependency_graph(self) -> None:
        """保存依赖图。"""
        if not self._ensure_graph_canvas():
            return

        if not self.graph_canvas.figure.axes:
            QMessageBox.information(self, "提示", "当前没有可保存的图表。")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存依赖图",
            os.path.join(os.path.expanduser("~"), "dependency_graph.png"),
            "PNG Files (*.png);;All Files (*)"
        )
        if not file_path:
            return

        try:
            self.graph_canvas.figure.savefig(file_path, dpi=180, bbox_inches="tight")
            QMessageBox.information(self, "保存成功", f"图表已保存至:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存图表失败: {e}")

    def toggle_tail(self) -> None:
        """切换日志跟踪状态。"""
        if self._tail_running:
            self._tail_running = False
            self._tail_stop_event.set()
            self._set_status_text("状态: 日志跟踪已停止")
            return

        if not self.file_path or not os.path.exists(self.file_path):
            QMessageBox.information(self, "提示", "请先加载一个有效的本地日志文件。")
            return

        self._tail_running = True
        self._tail_stop_event.clear()
        self._set_status_text("状态: 正在跟踪日志变化...")
        threading.Thread(target=self._tail_worker, daemon=True).start()

    def _tail_worker(self) -> None:
        """日志跟踪工作线程。"""
        try:
            with open(self.file_path, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(0, 2)
                while not self._tail_stop_event.is_set():
                    line = f.readline()
                    if line:
                        self.tail_line_signal.emit(line)
                    else:
                        time.sleep(0.4)
        except Exception as e:
            self.tail_line_signal.emit(f"\n[tail错误] {e}\n")
        finally:
            self._tail_running = False

    def _append_tail_line(self, line: str) -> None:
        """追加日志行。"""
        self.log_text_edit.moveCursor(self.log_text_edit.textCursor().MoveOperation.End)
        self.log_text_edit.insertPlainText(line)
        self.log_text_edit.ensureCursorVisible()
        current = self.log_service.get_text() or ""
        self.log_service.set_log_text(current + line)

    def launch_adversarial_gen(self) -> None:
        """启动场景生成器。"""
        script_path = os.path.join(ROOT_DIR, "tools", "generate_mc_log.py")
        if not os.path.exists(script_path):
            QMessageBox.warning(self, "启动失败", f"未找到脚本: {script_path}")
            return

        try:
            import subprocess
            if os.name == "nt":
                subprocess.Popen([
                    "cmd", "/c", "start", "cmd", "/k", f'"{sys.executable}" "{script_path}" --help'
                ], creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            else:
                subprocess.Popen([sys.executable, script_path, "--help"])
            QMessageBox.information(self, "已启动", "场景生成器已在新终端中启动。")
        except Exception as e:
            QMessageBox.critical(self, "启动失败", str(e))

    def launch_gpu_setup(self) -> None:
        """启动 GPU 配置向导。"""
        script_path = os.path.join(ROOT_DIR, "tools", "gpu_setup.py")
        if not os.path.exists(script_path):
            QMessageBox.warning(self, "启动失败", f"未找到脚本: {script_path}")
            return

        try:
            import subprocess
            if os.name == "nt":
                subprocess.Popen([
                    "cmd", "/c", "start", "cmd", "/k", f'"{sys.executable}" "{script_path}"'
                ], creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            else:
                subprocess.Popen([sys.executable, script_path])
            QMessageBox.information(self, "已启动", "GPU 配置向导已在新终端中启动。")
        except Exception as e:
            QMessageBox.critical(self, "启动失败", str(e))

    def set_graph_layout(self, layout_name: str) -> None:
        """设置图表布局。"""
        self.graph_layout_name = layout_name
        if self.current_dep_pairs or self.current_cause_counts:
            self.draw_graphs(self.current_dep_pairs, self.current_cause_counts)

    def set_filter_isolated(self, checked: bool) -> None:
        """设置是否过滤孤立节点。"""
        self.filter_isolated_nodes = bool(checked)
        if self.current_dep_pairs or self.current_cause_counts:
            self.draw_graphs(self.current_dep_pairs, self.current_cause_counts)

    def refresh_hardware_analysis(self) -> None:
        """刷新硬件分析。"""
        text = self.log_text_edit.toPlainText() or ""
        system_info: dict[str, Any] = {}
        try:
            system_info = SystemService().get_system_info()
        except Exception:
            system_info = {}

        gpu_rules: dict[str, Any] = {}
        try:
            if os.path.exists(GPU_ISSUES_FILE):
                with open(GPU_ISSUES_FILE, "r", encoding="utf-8") as fp:
                    loaded = json.load(fp)
                    if isinstance(loaded, dict):
                        gpu_rules = loaded
        except Exception:
            gpu_rules = {}

        result = analyze_hardware_log(
            text,
            current_mods=self.current_mods,
            system_info=system_info,
            gpu_rules=gpu_rules,
            max_snippets=24,
        )

        self.hardware_issues = result["suggestions"]
        self.gl_snippets = result["snippets"]

        risk_map = {
            "HIGH": "高",
            "MEDIUM": "中",
            "LOW": "低",
            "NONE": "无",
        }

        def _fmt_mem_gb(value: Any) -> str:
            try:
                num = int(value)
                if num <= 0:
                    return "未知"
                return f"{num / (1024 ** 3):.1f} GB"
            except Exception:
                return "未知"

        report_lines: list[str] = []
        report_lines.append("硬件分析报告")
        report_lines.append("=" * 50)

        if system_info:
            report_lines.append("系统概览:")
            report_lines.append(f"- 平台: {system_info.get('platform', '未知')}")
            report_lines.append(f"- Python: {system_info.get('python', '未知')}")
            report_lines.append(f"- 物理核心: {system_info.get('cpu_count', '未知')}")
            report_lines.append(f"- 总内存: {_fmt_mem_gb(system_info.get('memory_total'))}")

            gpus = system_info.get("gpus")
            if isinstance(gpus, list) and gpus:
                report_lines.append("- GPU:")
                for gpu in gpus:
                    if isinstance(gpu, dict):
                        name = gpu.get("name", "Unknown")
                        driver = gpu.get("driver", "Unknown")
                        memory = gpu.get("memoryTotal")
                        memory_txt = f"{memory} MB" if memory is not None else "未知"
                        report_lines.append(f"  * {name} | Driver: {driver} | VRAM: {memory_txt}")

        report_lines.append("")
        report_lines.append("风险评估:")
        report_lines.append(
            f"- 级别: {risk_map.get(result['risk_level'], '无')} | 分数: {result['risk_score']}"
        )

        categories = result.get("categories") or []
        if categories:
            report_lines.append(f"- 命中类型: {', '.join(categories)}")

        issues = result.get("issues") or []
        if issues:
            report_lines.append("")
            report_lines.append("诊断命中:")
            for issue in issues:
                category = issue.get("category", "未分类")
                evidence = issue.get("evidence", "")
                report_lines.append(f"- [{category}] {evidence}")

        render_mods = result.get("render_mods") or []
        if render_mods:
            report_lines.append("")
            report_lines.append("可疑渲染模组:")
            report_lines.append("- " + ", ".join(render_mods))

        suggestions = result.get("suggestions") or []
        if suggestions:
            report_lines.append("")
            report_lines.append("建议动作:")
            for tip in suggestions:
                report_lines.append(f"- {tip}")

        snippets = result.get("snippets") or []
        if snippets:
            report_lines.append("")
            report_lines.append("GL/渲染证据片段:")
            report_lines.extend(snippets)

        if not issues and not snippets:
            report_lines.append("")
            report_lines.append("未发现明显的硬件/渲染异常特征。")

        self.hardware_text_edit.setPlainText("\n".join(report_lines))
        self.tabs.setCurrentIndex(3)

    def copy_gl_snippets(self) -> None:
        """复制 GL 片段。"""
        if not self.gl_snippets:
            QMessageBox.information(self, "提示", "当前没有可复制的 GL 片段。")
            return

        text = "\n---\n".join(self.gl_snippets)
        from PyQt6.QtWidgets import QApplication
        cb = QApplication.clipboard()
        cb.setText(text)
        QMessageBox.information(self, "复制成功", "GL 片段已复制到剪贴板。")

    def start_auto_test(self) -> None:
        """开始自动化测试。"""
        output_dir = self.auto_test_output_edit.text().strip() or os.path.join(ROOT_DIR, "tmp", "autotests")
        os.makedirs(output_dir, exist_ok=True)

        selected = self.auto_test_scenarios.selectedItems()
        scenarios = [item.text().split("-")[0].strip() for item in selected]
        if not scenarios:
            scenarios = ["normal"]

        count = int(self.auto_test_count_spin.value())
        cleanup = bool(self.auto_test_cleanup_check.isChecked())
        run_analysis = bool(self.auto_test_run_analysis_check.isChecked())

        self.auto_test_log_edit.clear()
        self.auto_test_progress.setValue(0)
        self.auto_test_progress.setMaximum(max(count, 1))
        self.btn_auto_test_start.setEnabled(False)
        self.btn_auto_test_stop.setEnabled(True)
        self.auto_test_stats_label.setText("统计: 运行中...")
        self.tabs.setCurrentIndex(4)

        worker = AutoTestWorker(
            output_dir, 
            scenarios, 
            count, 
            cleanup,
            engine=self.engine,
            run_analysis=run_analysis
        )
        worker.signals.log.connect(self.auto_test_log_edit.append)
        worker.signals.progress.connect(lambda cur, total: self.auto_test_progress.setValue(cur))
        worker.signals.stats.connect(self.on_auto_test_stats)
        worker.signals.error.connect(self.on_auto_test_error)
        worker.signals.finished.connect(self.on_auto_test_finished)
        self.auto_test_worker = worker
        worker.start()

    def stop_auto_test(self) -> None:
        """停止自动化测试。"""
        if self.auto_test_worker:
            self.auto_test_worker.cancel()
            self.auto_test_log_edit.append("用户请求停止自动化测试...")

    def on_auto_test_stats(self, gen_time: str, samples: str, cleanup_msg: str) -> None:
        """处理自动化测试统计。"""
        self.auto_test_stats_label.setText(f"统计: 生成耗时 {gen_time}, 样本数 {samples}, {cleanup_msg}")

    def on_auto_test_error(self, msg: str) -> None:
        """处理自动化测试错误。"""
        self.auto_test_log_edit.append(f"[错误] {msg}")

    def on_auto_test_finished(self) -> None:
        """处理自动化测试完成。"""
        self.btn_auto_test_start.setEnabled(True)
        self.btn_auto_test_stop.setEnabled(False)
        self.auto_test_log_edit.append("自动化测试结束。")
        self.auto_test_worker = None

    def start_ai_init_if_needed(self) -> None:
        """启动 AI 引擎初始化。"""
        if self.brain is not None:
            QMessageBox.information(self, "提示", "AI 分析引擎已处于启动状态。")
            return
        if not HAS_BRAIN or not HAS_BRAIN_CORE:
            QMessageBox.warning(self, "不可用", "当前环境未安装 BrainCore，无法启动 AI 引擎。")
            return

        self.btn_start_ai.setEnabled(False)
        self.btn_start_ai.setText("启动中...")
        self._set_brain_monitor_state("loading")
        self._set_status_text("状态: 正在启动 AI 分析引擎并预热语义模型...")

        worker = AIInitWorker(self._brain_config_path)
        worker.signals.done.connect(self.on_ai_init_done)
        self.ai_init_worker = worker
        worker.start()

    def on_ai_init_done(self, ok: bool, payload: Any) -> None:
        """处理 AI 引擎初始化完成。"""
        self.btn_start_ai.setEnabled(True)
        if ok:
            self.brain = payload
            self.btn_start_ai.setText("AI已启动")
            self.btn_start_ai.setEnabled(False)
            self._set_brain_monitor_state("active")
            self._set_status_text("状态: AI 引擎与语义模型已就绪")
            QMessageBox.information(self, "成功", "AI 分析引擎启动完成，语义模型已预热。")
        else:
            self.btn_start_ai.setText("启动AI")
            self._set_brain_monitor_state("error")
            self._set_status_text("状态: AI 引擎启动失败")
            QMessageBox.warning(self, "启动失败", f"无法启动 AI 引擎: {payload}")

    def view_history(self) -> None:
        """查看分析历史。"""
        history_file = HISTORY_FILE
        if not os.path.exists(history_file):
            QMessageBox.information(self, "历史记录", "暂无分析历史记录。")
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle("分析历史记录")
        dialog.resize(800, 400)
        dialog.setStyleSheet(self.styleSheet())
        
        layout = QVBoxLayout(dialog)
        
        tree = QTreeWidget()
        tree.setHeaderLabels(["时间", "摘要", "文件路径"])
        tree.setColumnWidth(0, 150)
        tree.setColumnWidth(1, 400)
        tree.setColumnWidth(2, 200)
        
        try:
            with open(history_file, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                rows = list(reader)
                for row in reversed(rows):
                    if len(row) >= 3:
                        item = QTreeWidgetItem(row[:3])
                        tree.addTopLevelItem(item)
        except Exception as e:
            QMessageBox.warning(self, "读取失败", f"无法读取历史记录: {e}")
            return
            
        tree.itemDoubleClicked.connect(lambda item, col: self.load_log_from_history(item.text(2), dialog))
        layout.addWidget(tree)
        dialog.exec()

    def load_log_from_history(self, filepath: str, dialog: QDialog) -> None:
        """从历史记录加载日志。"""
        if not os.path.exists(filepath):
            QMessageBox.warning(dialog, "文件不存在", f"无法找到日志文件: {filepath}")
            return
        
        self.load_log_file(filepath)
        dialog.accept()

    def show_about(self) -> None:
        """显示关于对话框。"""
        QMessageBox.about(
            self,
            "关于 MCA 智脑系统",
            "<h2>Minecraft 崩溃日志分析系统</h2>"
            "<p><b>版本:</b> 2.0 (PyQt6 Silicone UI)</p>"
            "<p>具有智能诊断和图谱分析功能的下一代崩溃分析工具。</p>"
            "<p>UI 设计: Neumorphic (硅胶/胶囊拟态)</p>"
        )

    def setup_ui(self) -> None:
        """设置 UI。"""
        self.central_widget = QWidget(self)
        self.central_widget.setObjectName("mainContainer")
        self.setCentralWidget(self.central_widget)
        
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(25, 25, 25, 25)
        self.main_layout.setSpacing(20)
        
        self._setup_header()
        self._setup_toolbar()
        self._setup_splitter()

    def _setup_header(self) -> None:
        """设置标题。"""
        self.header_label = QLabel("Minecraft 崩溃日志分析系统 (PyQt6)")
        self.header_label.setStyleSheet("font-size: 26px; font-weight: bold; color: #2d3748;")
        self.main_layout.addWidget(self.header_label, alignment=Qt.AlignmentFlag.AlignCenter)

    def _setup_toolbar(self) -> None:
        """设置工具栏。"""
        self.toolbar_layout = QHBoxLayout()
        self.toolbar_layout.setSpacing(15)
        
        self.btn_load = QPushButton("加载日志")
        self.btn_load.clicked.connect(self.on_load_clicked)
        
        self.btn_analyze = QPushButton("开始智能分析")
        self.btn_analyze.setObjectName("accentButton")
        self.btn_analyze.clicked.connect(self.on_analyze_clicked)
        self.btn_analyze.setEnabled(False)
        
        self.btn_settings = QPushButton("系统设置")
        self.btn_settings.clicked.connect(self.on_settings_clicked)

        self.btn_start_ai = QPushButton("启动AI")
        self.btn_start_ai.clicked.connect(self.start_ai_init_if_needed)
        
        exact_version = platform.python_version()
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #718096; font-style: italic;")

        self.brain_monitor = None
        if BrainMonitorWidget is not None:
            try:
                self.brain_monitor = BrainMonitorWidget(self)
            except Exception:
                self.brain_monitor = None
        
        self.toolbar_layout.addWidget(self.btn_load)
        self.toolbar_layout.addWidget(self.btn_analyze)
        self.toolbar_layout.addWidget(self.btn_start_ai)
        self.toolbar_layout.addWidget(self.btn_settings)
        self.toolbar_layout.addWidget(self.status_label)
        if self.brain_monitor is not None:
            self.toolbar_layout.addWidget(self.brain_monitor)
        self.toolbar_layout.addStretch()
        self.main_layout.addLayout(self.toolbar_layout)
        self._set_status_text(f"状态: 等待加载日志... | 核心驱动: Python {exact_version}")

    def _setup_splitter(self) -> None:
        """设置分割器。"""
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self._setup_log_card()
        self._setup_right_card()
        
        self.splitter.addWidget(self.log_card)
        self.splitter.addWidget(self.right_card)
        self.splitter.setSizes([500, 700])
        self.splitter.setStretchFactor(0, 5)
        self.splitter.setStretchFactor(1, 7)
        self.splitter.setHandleWidth(8)

        self.main_layout.addWidget(self.splitter, stretch=1)

    def _setup_log_card(self) -> None:
        """设置日志卡片。"""
        self.log_card = QFrame()
        self.log_card.setObjectName("siliconeCard")
        shadow1 = QGraphicsDropShadowEffect()
        shadow1.setBlurRadius(20)
        shadow1.setXOffset(5)
        shadow1.setYOffset(5)
        shadow1.setColor(QColor(163, 177, 198, 120))
        self.log_card.setGraphicsEffect(shadow1)
        self.log_layout = QVBoxLayout(self.log_card)
        
        log_title = QLabel("📄 崩溃日志原文")
        log_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.log_text_edit = QTextEdit()
        self.log_text_edit.setReadOnly(True)
        self.log_text_edit.setPlaceholderText("请点击上方「加载日志」按钮...")
        self.log_text_edit.setStyleSheet("font-family: Consolas, monospace; font-size: 12px; background: transparent; border: none;")
        
        self.log_layout.addWidget(log_title)
        self.log_layout.addWidget(self.log_text_edit)

    def _setup_right_card(self) -> None:
        """设置右侧卡片。"""
        self.right_card = QFrame()
        self.right_card.setObjectName("siliconeCard")
        shadow2 = QGraphicsDropShadowEffect()
        shadow2.setBlurRadius(20)
        shadow2.setXOffset(5)
        shadow2.setYOffset(5)
        shadow2.setColor(QColor(163, 177, 198, 120))
        self.right_card.setGraphicsEffect(shadow2)
        self.right_layout = QVBoxLayout(self.right_card)
        
        self._setup_tabs()
        
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setFixedHeight(8)
        self.progress.hide()
        
        self.right_layout.addWidget(self.tabs)
        self.right_layout.addWidget(self.progress)

    def _setup_tabs(self) -> None:
        """设置标签页。"""
        self.tabs = QTabWidget()
        self.tabs.setCursor(Qt.CursorShape.ArrowCursor)
        
        self._setup_results_tab()
        self._setup_mods_tab()
        self._setup_graphs_tab()
        self._setup_hardware_tab()
        self._setup_auto_test_tab()

    def _setup_results_tab(self) -> None:
        """设置结果标签页。"""
        self.tab_results = QWidget()
        self.tab_results_layout = QVBoxLayout(self.tab_results)
        self.result_text_edit = QTextEdit()
        self.result_text_edit.setReadOnly(True)
        self.result_text_edit.setStyleSheet("font-family: Consolas, monospace; font-size: 14px; color: #2c5282; border: none; background: transparent;")
        self.tab_results_layout.addWidget(self.result_text_edit)

    def _setup_mods_tab(self) -> None:
        """设置模组标签页。"""
        self.tab_mods = QWidget()
        self.tab_mods_layout = QVBoxLayout(self.tab_mods)
        self.mod_list_widget = QListWidget()
        self.mod_list_widget.setStyleSheet("border: none; background: transparent; font-size: 13px;")
        self.tab_mods_layout.addWidget(self.mod_list_widget)

    def _setup_graphs_tab(self) -> None:
        """设置图表标签页。"""
        self.tab_graphs = QWidget()
        self.tab_graphs_layout = QVBoxLayout(self.tab_graphs)
        self._graph_placeholder = QLabel("图表模块将在首次绘制时初始化")
        self._graph_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._graph_placeholder.setStyleSheet("color: #718096; font-style: italic;")
        self.tab_graphs_layout.addWidget(self._graph_placeholder)

    def _setup_hardware_tab(self) -> None:
        """设置硬件标签页。"""
        self.tab_hardware = QWidget()
        self.tab_hardware_layout = QVBoxLayout(self.tab_hardware)
        self.hardware_text_edit = QTextEdit()
        self.hardware_text_edit.setReadOnly(True)
        self.hardware_text_edit.setPlaceholderText("分析后显示硬件/GL 相关建议...")
        self.hardware_text_edit.setStyleSheet("font-family: Consolas, monospace; font-size: 12px; border: none; background: transparent;")
        self.tab_hardware_layout.addWidget(self.hardware_text_edit)

    def _setup_auto_test_tab(self) -> None:
        """设置自动测试标签页。"""
        self.tab_auto_test = QWidget()
        self.tab_auto_test_layout = QVBoxLayout(self.tab_auto_test)

        auto_form = QFormLayout()
        self.auto_test_output_edit = QLineEdit(os.path.join(ROOT_DIR, "tmp", "autotests"))
        self.auto_test_output_edit.setPlaceholderText("自动生成日志输出目录")
        auto_form.addRow(QLabel("输出目录:"), self.auto_test_output_edit)

        self.auto_test_count_spin = QSpinBox()
        self.auto_test_count_spin.setRange(1, 5000)
        self.auto_test_count_spin.setValue(10)
        auto_form.addRow(QLabel("生成数量:"), self.auto_test_count_spin)

        self.auto_test_run_analysis_check = QCheckBox("生成后自动执行分析")
        self.auto_test_run_analysis_check.setChecked(True)
        auto_form.addRow(QLabel("分析模式:"), self.auto_test_run_analysis_check)

        self.auto_test_cleanup_check = QCheckBox("完成后自动清理生成文件")
        self.auto_test_cleanup_check.setChecked(True)
        auto_form.addRow(QLabel("清理选项:"), self.auto_test_cleanup_check)
        self.tab_auto_test_layout.addLayout(auto_form)

        self.auto_test_scenarios = QListWidget()
        self.auto_test_scenarios.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        scenario_map = SCENARIOS if SCENARIOS else {
            "normal": "正常日志",
            "version_conflict": "版本冲突",
            "missing_dependency": "缺失前置",
            "mixin_conflict": "Mixin 注入失败",
            "ticking_entity": "实体更新错误",
            "out_of_memory": "内存溢出",
            "bad_video_driver": "显卡驱动不兼容",
        }
        for key, desc in scenario_map.items():
            self.auto_test_scenarios.addItem(f"{key} - {desc}")
        for i in range(self.auto_test_scenarios.count()):
            self.auto_test_scenarios.item(i).setSelected(True)
        self.tab_auto_test_layout.addWidget(QLabel("测试场景 (可多选):"))
        self.tab_auto_test_layout.addWidget(self.auto_test_scenarios)

        auto_btns = QHBoxLayout()
        self.btn_auto_test_start = QPushButton("开始自动化测试")
        self.btn_auto_test_start.clicked.connect(self.start_auto_test)
        self.btn_auto_test_stop = QPushButton("停止")
        self.btn_auto_test_stop.clicked.connect(self.stop_auto_test)
        self.btn_auto_test_stop.setEnabled(False)
        auto_btns.addWidget(self.btn_auto_test_start)
        auto_btns.addWidget(self.btn_auto_test_stop)
        auto_btns.addStretch()
        self.tab_auto_test_layout.addLayout(auto_btns)

        self.auto_test_progress = QProgressBar()
        self.auto_test_progress.setValue(0)
        self.tab_auto_test_layout.addWidget(self.auto_test_progress)

        self.auto_test_stats_label = QLabel("统计: 生成耗时 -, 样本数 -, 清理状态 -")
        self.tab_auto_test_layout.addWidget(self.auto_test_stats_label)

        self.auto_test_log_edit = QTextEdit()
        self.auto_test_log_edit.setReadOnly(True)
        self.auto_test_log_edit.setPlaceholderText("自动化测试日志输出...")
        self.auto_test_log_edit.setStyleSheet("font-family: Consolas, monospace; font-size: 12px; border: none; background: transparent;")
        self.tab_auto_test_layout.addWidget(self.auto_test_log_edit)
        
        self.tabs.addTab(self.tab_results, "🧠 诊断报告")
        self.tabs.addTab(self.tab_mods, "📦 环境与模组")
        self.tabs.addTab(self.tab_graphs, "📊 依赖图表")
        self.tabs.addTab(self.tab_hardware, "🖥️ 硬件分析")
        self.tabs.addTab(self.tab_auto_test, "🧪 自动化测试")

    def on_settings_clicked(self) -> None:
        """处理设置按钮点击。"""
        from mca_core.python_runtime_optimizer import apply_version_specific_optimizations
        
        dialog = QDialog(self)
        dialog.setWindowTitle("系统设置")
        dialog.resize(520, 300)
        dialog.setStyleSheet(self.styleSheet())
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        
        form_layout = QFormLayout()

        scroll_spin = QSpinBox()
        scroll_spin.setRange(1, 50)
        scroll_spin.setValue(self.config_service.get_scroll_sensitivity())
        form_layout.addRow(QLabel("滚动灵敏度:"), scroll_spin)

        highlight_spin = QSpinBox()
        highlight_spin.setRange(100, 200000)
        highlight_spin.setSingleStep(100)
        highlight_spin.setValue(self.config_service.get_highlight_size_limit())
        form_layout.addRow(QLabel("高亮大小阈值:"), highlight_spin)
        
        mode_combo = QComboBox()
        for mode, desc in MODE_DESCRIPTIONS:
            mode_combo.addItem(f"{mode} - {desc}", mode)
        mode_combo.setCurrentIndex(1)
        form_layout.addRow(QLabel("运行时优化模式:"), mode_combo)
        
        layout.addLayout(form_layout)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_mode = mode_combo.currentData()
            try:
                self.config_service.set_scroll_sensitivity(scroll_spin.value())
                self.config_service.set_highlight_size_limit(highlight_spin.value())
                self.config_service.save()
                apply_version_specific_optimizations(selected_mode)
                QMessageBox.information(self, "设置已保存", f"已应用 {selected_mode} 模式的运行时优化。")
            except Exception as e:
                QMessageBox.warning(self, "设置失败", f"应用优化失败: {str(e)}")

    def on_load_clicked(self) -> None:
        """处理加载按钮点击。"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择崩溃日志文件", "", "日志文件 (*.log *.txt);;所有文件 (*.*)"
        )
        if file_path:
            self.load_log_file(file_path)

    def load_log_file(self, file_path: str) -> None:
        """
        加载日志文件。
        
        Args:
            file_path: 日志文件路径
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            self.log_service.set_log_text(content)
            self.file_path = file_path
            self.log_text_edit.setPlainText(content)
            self._set_status_text(f"状态: 已加载 {os.path.basename(file_path)}")
            self.btn_analyze.setEnabled(True)
            self.result_text_edit.clear()
            self.mod_list_widget.clear()
            if self.graph_canvas is not None:
                self.graph_canvas.figure.clear()
                self.graph_canvas.draw()
        except Exception as e:
            QMessageBox.critical(self, "加载错误", f"无法加载文件: {e}")

    def import_mods(self) -> None:
        """导入模组列表。"""
        folder = QFileDialog.getExistingDirectory(self, "选择 .minecraft/mods 文件夹")
        if not folder:
            return

        mods: dict[str, set] = defaultdict(set)
        pattern = re.compile(r"([a-zA-Z0-9_\-]+)-(\d[\w\.\-]+)\.jar")

        try:
            for root, _, files in os.walk(folder):
                for name in files:
                    if not name.lower().endswith(".jar"):
                        continue
                    m = pattern.search(name)
                    if not m:
                        continue
                    mods[m.group(1)].add(m.group(2))

            self.current_mods = dict(mods)
            self.mod_list_widget.clear()
            self.mod_list_widget.addItem(f"从目录导入 {len(mods)} 个模组:")
            for modid, versions in sorted(mods.items()):
                self.mod_list_widget.addItem(f"📦 {modid} (版本: {', '.join(sorted(versions))})")

            self.tabs.setCurrentIndex(1)
            self._set_status_text(f"状态: 已导入 {len(mods)} 个模组")
            QMessageBox.information(self, "导入完成", f"在文件夹中发现 {len(mods)} 个模组。")
        except Exception as e:
            QMessageBox.critical(self, "导入失败", f"扫描失败: {e}")

    def on_analyze_clicked(self) -> None:
        """处理分析按钮点击。"""
        log_text = self.log_text_edit.toPlainText()
        if not log_text:
            return
            
        self.btn_analyze.setEnabled(False)
        self.btn_load.setEnabled(False)
        self.result_text_edit.clear()
        self.mod_list_widget.clear()
        if self.graph_canvas is not None:
            self.graph_canvas.figure.clear()
            self.graph_canvas.draw()
        
        self.result_text_edit.append("开始执行深度诊断流程...\n" + "="*40)
        self.progress.show()
        self.progress.setValue(0)
        self._set_brain_monitor_state("loading")
        self._set_status_text("状态: 分析中...")
        self.tabs.setCurrentIndex(0)
        
        self.worker = AnalysisWorker(self.engine, self.brain, log_text)
        self.worker.signals.progress.connect(self.on_analysis_progress)
        self.worker.signals.append_log.connect(self.on_analysis_append)
        self.worker.signals.finished.connect(self.on_analysis_finished)
        self.worker.signals.error.connect(self.on_analysis_error)
        self.worker.start()

    def on_analysis_progress(self, val: int, msg: str) -> None:
        """处理分析进度更新。"""
        self.progress.setValue(val)
        self._set_status_text(f"状态: {msg}")

    def on_analysis_append(self, msg: str) -> None:
        """处理分析日志追加。"""
        self.result_text_edit.append(msg)

    def on_analysis_finished(
        self,
        result_text: str,
        dep_pairs: set[tuple[str, str]],
        mods: dict[str, set],
        cause_counts: dict[str, int]
    ) -> None:
        """处理分析完成。"""
        self.current_dep_pairs = set(dep_pairs or set())
        self.current_mods = dict(mods or {})
        self.current_cause_counts = dict(cause_counts or {})

        self.result_text_edit.append("\n" + "="*40 + "\n[最终诊断结果总结]\n")
        self.result_text_edit.append(result_text)
        
        self.mod_list_widget.addItem(f"检测到 {len(mods)} 个独立模组:")
        for modid, vers in sorted(mods.items()):
            v_str = ", ".join(vers)
            self.mod_list_widget.addItem(f"📦 {modid} (版本: {v_str})")
            
        self.draw_graphs(dep_pairs, cause_counts)
        self.refresh_hardware_analysis()
        
        self.finish_analysis()
        self._set_brain_monitor_state("active")
        self._set_status_text("状态: 分析完成！")

    def draw_graphs(
        self,
        dep_pairs: set[tuple[str, str]],
        cause_counts: dict[str, int]
    ) -> None:
        """绘制图表。"""
        if not self._ensure_graph_canvas():
            return

        if not HAS_NX or nx is None:
            return

        fig = self.graph_canvas.figure
        fig.clear()
        
        if cause_counts:
            ax = fig.add_subplot(121)
            ax.set_title("崩溃原因统计", fontdict={'family': 'SimHei' if sys.platform == 'win32' else 'sans-serif'})
            labels = list(cause_counts.keys())
            sizes = list(cause_counts.values())
            ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=['#4fd1c5', '#f6ad55', '#fc8181', '#f687b3'])
            ax.axis('equal')
            ax2 = fig.add_subplot(122)
        else:
            ax2 = fig.add_subplot(111)
            
        ax2.set_title("核心依赖关系网络", fontdict={'family': 'SimHei' if sys.platform == 'win32' else 'sans-serif'})
        if dep_pairs:
            G = nx.DiGraph()
            for src, dst in dep_pairs:
                G.add_edge(src, dst)
            if self.filter_isolated_nodes:
                try:
                    isolates = list(nx.isolates(G))
                    G.remove_nodes_from(isolates)
                except Exception:
                    pass
            pos = nx.spring_layout(G, seed=42)
            if self.graph_layout_name == "circular":
                pos = nx.circular_layout(G)
            elif self.graph_layout_name == "shell":
                pos = nx.shell_layout(G)
            elif self.graph_layout_name == "spectral":
                pos = nx.spectral_layout(G)
            elif self.graph_layout_name == "random":
                pos = nx.random_layout(G)
            nx.draw(G, pos, ax=ax2, with_labels=True, node_color='#d1d9e6', 
                    node_size=800, font_size=8, font_weight='bold', edge_color='#a0aec0',
                    arrowsize=10, font_family='Consolas')
        else:
            ax2.text(0.5, 0.5, "未检测到明确的依赖问题", ha='center', va='center', color='#718096')
            ax2.axis('off')
            
        fig.tight_layout()
        self.graph_canvas.draw()

    def on_analysis_error(self, err_msg: str) -> None:
        """处理分析错误。"""
        self.result_text_edit.append(f"\n[错误] 分析过程中断: {err_msg}")
        self.finish_analysis()
        self._set_brain_monitor_state("error")
        self._set_status_text("状态: 分析出错")

    def finish_analysis(self) -> None:
        """完成分析。"""
        self.btn_analyze.setEnabled(True)
        self.btn_load.setEnabled(True)
        self.progress.hide()
