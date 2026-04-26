"""
GUI 主入口 (重构版)

使用 Mixin 模式组合各功能模块。
详细逻辑已拆分到 app_*_mixin.py 文件中。

架构说明:
    MinecraftCrashAnalyzer 是主应用类，通过多重继承组合以下 Mixin:
    - AnalysisEventMixin: 分析事件处理
    - SettingsMixin: 设置管理
    - LabMixin: 实验室功能
    - InitializationMixin: 初始化逻辑
    - FileOpsMixin: 文件操作
    - AnalysisMixin: 核心分析逻辑
    - GraphMixin: 图表可视化
    - UIMixin: UI 创建和管理
    - AutoTestMixin: 自动化测试
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from collections import Counter, defaultdict, OrderedDict
from typing import TYPE_CHECKING, Any, Optional

import tkinter as tk

if TYPE_CHECKING:
    from brain_system.core import BrainCore
    from config.app_config import AppConfig
    from mca_core.detectors import DetectorRegistry
    from mca_core.module_loader import ModuleLoader
    from mca_core.plugins import PluginRegistry
    from mca_core.services.config_service import ConfigService
    from mca_core.services.database import DatabaseManager
    from mca_core.services.log_service import LogService
    from mca_core.services.system_service import SystemService
    from mca_core.learning import CrashPatternLearner
    from mca_core.di import DIContainer

SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR: str = os.path.dirname(SCRIPT_DIR)

from config.constants import (
    BASE_DIR,
    CONFIG_FILE,
    WINDOW_DEFAULT_SIZE,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
    WINDOW_TITLE,
)
from mca_core.app_analysis_mixin import AnalysisMixin
from mca_core.app_auto_test_mixin import AutoTestMixin
from mca_core.app_file_ops_mixin import FileOpsMixin
from mca_core.app_graph_mixin import GraphMixin
from mca_core.app_initialization_mixin import InitializationMixin
from mca_core.app_ui_mixin import UIMixin
from mca_core.detectors import DetectorRegistry
from mca_core.di import DIContainer
from mca_core.module_loader import ModuleLoader
from mca_core.plugins import PluginRegistry
from mca_core.python_runtime_optimizer import apply_version_specific_optimizations
from mca_core.services.config_service import ConfigService
from mca_core.services.database import DatabaseManager
from mca_core.services.log_service import LogService
from mca_core.services.system_service import SystemService
from mca_core.ui_mixins import AnalysisEventMixin
from mca_core.settings_mixins import SettingsMixin
from mca_core.lab_mixins import LabMixin
from utils.helpers import mca_clean_modid, mca_normalize_modid

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger(__name__)

try:
    from brain_system.core import BrainCore
    HAS_BRAIN: bool = True
except ImportError:
    HAS_BRAIN = False
    BrainCore: type | None = None

BRAIN_SYSTEM_DIR: str = ROOT_DIR


class MinecraftCrashAnalyzer(
    AnalysisEventMixin,
    SettingsMixin,
    LabMixin,
    InitializationMixin,
    FileOpsMixin,
    AnalysisMixin,
    GraphMixin,
    UIMixin,
    AutoTestMixin,
):
    """
    Minecraft 崩溃日志分析器主应用类。
    
    该类通过 Mixin 模式组合多个功能模块，提供完整的崩溃日志分析功能。
    
    Attributes:
        root: Tkinter 根窗口
        lock: 线程锁，用于保护共享状态
        log_service: 日志服务，管理日志文本
        config_service: 配置服务，管理应用配置
        system_service: 系统服务，获取系统信息
        database_manager: 数据库管理器，持久化分析结果
        container: 依赖注入容器
        detector_registry: 检测器注册表
        plugin_registry: 插件注册表
        brain: BrainCore AI 分析引擎实例
        analysis_results: 分析结果列表
        mods: 检测到的模组字典
        dependency_pairs: 依赖关系对集合
        cause_counts: 崩溃原因计数器
    """
    
    root: tk.Tk
    lock: threading.RLock
    log_service: LogService
    config_service: ConfigService
    system_service: SystemService
    database_manager: DatabaseManager
    container: DIContainer
    module_loader: ModuleLoader
    plugin_registry: PluginRegistry
    detector_registry: DetectorRegistry
    crash_pattern_learner: Any
    brain: Any
    analysis_results: list[str]
    mods: dict[str, set]
    mod_names: dict[str, str]
    dependency_pairs: set[tuple[str, str]]
    loader_type: Optional[str]
    cause_counts: Counter
    status_var: tk.StringVar
    _analysis_cache: OrderedDict
    _cache_max_size: int
    _tail_running: bool
    gl_snippets: list[str]
    gpu_info: dict[str, Any]
    hardware_issues: list[str]
    gpu_issues: dict[str, Any]
    _auto_test_cancel_event: threading.Event
    _auto_test_running: bool
    HAS_NEW_MODULES: bool
    _disabled_plugins: set[str]
    _brain_config_path: Optional[str]
    _brain_init_lock: threading.Lock
    _ai_init_started: bool

    def __init__(self, root: tk.Tk) -> None:
        """
        初始化崩溃分析器。
        
        Args:
            root: Tkinter 根窗口实例
        """
        apply_version_specific_optimizations()
        self._init_root_window(root)
        self._init_threading()
        self._init_services()
        self._init_cache()
        self._init_state()
        self._init_di_container()
        self._init_plugins()
        self._init_detectors()
        self._init_brain()
        self._setup_detectors()

    def _init_root_window(self, root: tk.Tk) -> None:
        """初始化根窗口配置。"""
        self.root = root
        self.root.title(WINDOW_TITLE)
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        default_w, default_h = map(int, WINDOW_DEFAULT_SIZE.split('x'))
        
        if screen_width < default_w or screen_height < default_h:
            adapt_w = int(screen_width * 0.8)
            adapt_h = int(screen_height * 0.8)
            self.root.geometry(f"{adapt_w}x{adapt_h}")
        else:
            self.root.geometry(WINDOW_DEFAULT_SIZE)
            
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

    def _init_threading(self) -> None:
        """初始化线程相关组件。"""
        self.lock = threading.RLock()
        self._auto_test_cancel_event = threading.Event()
        self._auto_test_running = False
        self._brain_init_lock = threading.Lock()
        self._ai_init_started = False

    def _init_services(self) -> None:
        """初始化服务层组件。"""
        self.log_service = LogService()
        self.config_service = ConfigService(CONFIG_FILE)
        self.system_service = SystemService()
        
        db_path = os.path.join(BASE_DIR, "mca_data.db")
        self.database_manager = DatabaseManager.get_instance(db_path)

    def _init_cache(self) -> None:
        """初始化缓存系统。"""
        self._analysis_cache = OrderedDict()
        self._cache_max_size = 100

    def _init_state(self) -> None:
        """初始化应用状态。"""
        self.analysis_results = []
        self.mods = defaultdict(set)
        self.mod_names = {}
        self.dependency_pairs = set()
        self.loader_type = None
        self.cause_counts = Counter()
        self.status_var = tk.StringVar(value="就绪")
        self._tail_running = False
        self.gl_snippets = []
        self.gpu_info = {}
        self.hardware_issues = []
        self.gpu_issues = {}
        self._disabled_plugins = set()

    def _init_di_container(self) -> None:
        """初始化依赖注入容器。"""
        self.container = DIContainer()
        self.container.register_instance("DatabaseManager", self.database_manager)
        self.module_loader = ModuleLoader(SCRIPT_DIR)
        self.HAS_NEW_MODULES = False

    def _init_plugins(self) -> None:
        """初始化插件系统。"""
        self.plugin_registry = PluginRegistry()
        try:
            plugins_dir = os.path.join(ROOT_DIR, "plugins")
            self.plugin_registry.load_from_directory(plugins_dir)
        except Exception:
            pass

    def _init_detectors(self) -> None:
        """初始化检测器注册表（单例模式）。"""
        self.detector_registry = DetectorRegistry.get_instance()
        self.crash_pattern_learner = None
        try:
            from mca_core.learning import CrashPatternLearner
            storage_path = os.path.join(BASE_DIR, "analysis_data", "learned_patterns.json")
            self.crash_pattern_learner = CrashPatternLearner(storage_path)
        except Exception:
            pass

    def _init_brain(self) -> None:
        """初始化 Brain AI 系统（延迟加载）。"""
        self.brain = None
        self._brain_config_path = None
        
        if HAS_BRAIN:
            brain_conf = os.path.join(BRAIN_SYSTEM_DIR, "config", "brain_config.json")
            if not os.path.exists(brain_conf):
                brain_conf_legacy = os.path.join(BRAIN_SYSTEM_DIR, "brain_config.json")
                brain_conf = brain_conf_legacy if os.path.exists(brain_conf_legacy) else None
            self._brain_config_path = brain_conf

    @property
    def file_path(self) -> str:
        """获取当前日志文件路径。"""
        return self.log_service.file_path

    @file_path.setter
    def file_path(self, value: str) -> None:
        """设置当前日志文件路径。"""
        self.log_service.file_path = value

    @property
    def file_checksum(self) -> Optional[str]:
        """获取当前日志文件的校验和。"""
        return self.log_service.file_checksum

    @file_checksum.setter
    def file_checksum(self, value: Optional[str]) -> None:
        """设置当前日志文件的校验和。"""
        self.log_service.file_checksum = value

    @property
    def crash_log(self) -> str:
        """获取当前崩溃日志文本。"""
        return self.log_service.get_text()

    @crash_log.setter
    def crash_log(self, value: str) -> None:
        """设置当前崩溃日志文本。"""
        self.log_service.set_log_text(value)

    def _invalidate_log_cache(self) -> None:
        """使日志缓存失效。"""
        self.log_service._invalidate_log_cache()

    def _get_log_text(self) -> str:
        """获取日志文本。"""
        return self.log_service.get_text()

    def _get_log_lower(self) -> str:
        """获取小写形式的日志文本。"""
        return self.log_service.get_lower()

    def _get_log_lines(self, lower: bool = False) -> list[str]:
        """获取日志行列表。"""
        return self.log_service.get_lines(lower)

    @property
    def scroll_sensitivity(self) -> int:
        """获取滚动灵敏度。"""
        return self.config_service.get_scroll_sensitivity()

    @scroll_sensitivity.setter
    def scroll_sensitivity(self, value: int) -> None:
        """设置滚动灵敏度。"""
        self.config_service.set_scroll_sensitivity(value)

    @property
    def highlight_size_limit(self) -> int:
        """获取高亮大小限制。"""
        return self.config_service.get_highlight_size_limit()

    @highlight_size_limit.setter
    def highlight_size_limit(self, value: int) -> None:
        """设置高亮大小限制。"""
        self.config_service.set_highlight_size_limit(value)

    def _load_config(self) -> None:
        """加载配置文件。"""
        self.config_service.load()

    def _save_config(self) -> None:
        """保存配置文件。"""
        self.config_service.save()

    def _is_cancelled(self) -> bool:
        """检查是否已请求取消操作。"""
        evt = getattr(self, "_cancel_event", None)
        return evt.is_set() if evt else False

    def _clean_modid(self, raw: str) -> str | None:
        """清理模组 ID。"""
        return mca_clean_modid(raw)

    def _normalize_modid(self, name: str) -> str | None:
        """规范化模组 ID。"""
        return mca_normalize_modid(name, self.mods.keys(), self.mod_names)

    def _collect_system_info(self) -> dict[str, Any]:
        """收集系统信息。"""
        return self.system_service.get_system_info()

    def _reload_config_if_changed(self) -> None:
        """如果配置文件已更改则重新加载。"""
        try:
            if getattr(self, "app_config", None):
                self.app_config = self.app_config.reload_if_changed(CONFIG_FILE)
        except Exception:
            pass
