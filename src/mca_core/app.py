"""
GUI 主入口 (重构版)

使用 Mixin 模式组合各功能模块。
详细逻辑已拆分到 app_*_mixin.py 文件中。
"""

import os
import sys
import threading
import logging
from collections import defaultdict, Counter
import tkinter as tk

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)

from config.constants import WINDOW_TITLE, WINDOW_DEFAULT_SIZE, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT, BASE_DIR, CONFIG_FILE
from mca_core.services.log_service import LogService
from mca_core.services.config_service import ConfigService
from mca_core.services.system_service import SystemService
from mca_core.services.database import DatabaseManager
from mca_core.module_loader import ModuleLoader
from mca_core.di import DIContainer
from mca_core.plugins import PluginRegistry
from mca_core.detectors import DetectorRegistry
from mca_core.python_runtime_optimizer import apply_version_specific_optimizations
from mca_core.ui_mixins import AnalysisEventMixin
from mca_core.settings_mixins import SettingsMixin
from mca_core.lab_mixins import LabMixin
from mca_core.app_initialization_mixin import InitializationMixin
from mca_core.app_file_ops_mixin import FileOpsMixin
from mca_core.app_analysis_mixin import AnalysisMixin
from mca_core.app_graph_mixin import GraphMixin
from mca_core.app_ui_mixin import UIMixin
from mca_core.app_auto_test_mixin import AutoTestMixin
from utils.helpers import mca_clean_modid, mca_normalize_modid

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger(__name__)

try:
    from brain_system.core import BrainCore
    HAS_BRAIN = True
except ImportError:
    HAS_BRAIN = False
    BrainCore = None

BRAIN_SYSTEM_DIR = ROOT_DIR


class MinecraftCrashAnalyzer(
    AnalysisEventMixin, SettingsMixin, LabMixin,
    InitializationMixin, FileOpsMixin, AnalysisMixin, GraphMixin, UIMixin, AutoTestMixin
):
    def __init__(self, root: tk.Tk):
        apply_version_specific_optimizations()
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry(WINDOW_DEFAULT_SIZE)
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        
        self.lock = threading.RLock()
        self.log_service = LogService()
        self.config_service = ConfigService(CONFIG_FILE)
        self.system_service = SystemService()
        
        db_path = os.path.join(BASE_DIR, "mca_data.db")
        self.database_manager = DatabaseManager.get_instance(db_path)
        
        # 缓存设置 (LRU 风格，限制大小)
        self._analysis_cache = {}
        self._cache_max_size = 100  # 最多缓存100个分析结果
        
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
        self._auto_test_cancel_event = threading.Event()
        self._auto_test_running = False
        
        self.container = DIContainer()
        self.container.register_instance("DatabaseManager", self.database_manager)
        self.module_loader = ModuleLoader(SCRIPT_DIR)
        self.HAS_NEW_MODULES = False
        
        self.plugin_registry = PluginRegistry()
        try:
            self.plugin_registry.load_from_directory(os.path.join(ROOT_DIR, "plugins"))
        except Exception:
            pass
        
        self.detector_registry = DetectorRegistry()
        self.crash_pattern_learner = None
        try:
            from mca_core.learning import CrashPatternLearner
            self.crash_pattern_learner = CrashPatternLearner(os.path.join(BASE_DIR, "analysis_data", "learned_patterns.json"))
        except Exception:
            pass
        
        # Brain 延迟初始化（避免启动时阻塞）
        self.brain = None
        self._brain_config_path = None
        self._brain_init_lock = threading.Lock()
        self._ai_init_started = False
        
        if HAS_BRAIN:
            # 仅记录配置路径，不创建 BrainCore 实例
            brain_conf = os.path.join(BRAIN_SYSTEM_DIR, "config", "brain_config.json")
            if not os.path.exists(brain_conf):
                brain_conf_legacy = os.path.join(BRAIN_SYSTEM_DIR, "brain_config.json")
                brain_conf = brain_conf_legacy if os.path.exists(brain_conf_legacy) else None
            self._brain_config_path = brain_conf
        
        self._setup_detectors()

    @property
    def file_path(self): return self.log_service.file_path
    @file_path.setter
    def file_path(self, v): self.log_service.file_path = v

    @property
    def file_checksum(self): return self.log_service.file_checksum
    @file_checksum.setter
    def file_checksum(self, v): self.log_service.file_checksum = v

    @property
    def crash_log(self): return self.log_service.get_text()
    @crash_log.setter
    def crash_log(self, v): self.log_service.set_log_text(v)

    def _invalidate_log_cache(self): self.log_service._invalidate_log_cache()
    def _get_log_text(self): return self.log_service.get_text()
    def _get_log_lower(self): return self.log_service.get_lower()
    def _get_log_lines(self, lower=False): return self.log_service.get_lines(lower)

    @property
    def scroll_sensitivity(self): return self.config_service.get_scroll_sensitivity()
    @scroll_sensitivity.setter
    def scroll_sensitivity(self, v): self.config_service.set_scroll_sensitivity(v)

    @property
    def highlight_size_limit(self): return self.config_service.get_highlight_size_limit()
    @highlight_size_limit.setter
    def highlight_size_limit(self, v): self.config_service.set_highlight_size_limit(v)

    def _load_config(self): self.config_service.load()
    def _save_config(self): self.config_service.save()

    def _is_cancelled(self):
        evt = getattr(self, "_cancel_event", None)
        return evt.is_set() if evt else False

    def _clean_modid(self, raw): return mca_clean_modid(raw)
    def _normalize_modid(self, name): return mca_normalize_modid(name, self.mods.keys(), self.mod_names)
    def _collect_system_info(self): return self.system_service.get_system_info()

    def _reload_config_if_changed(self):
        try:
            if getattr(self, "app_config", None):
                self.app_config = self.app_config.reload_if_changed(CONFIG_FILE)
        except Exception:
            pass
