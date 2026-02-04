"""Minecraft 崩溃分析工具 — UI 与分析逻辑聚合模块。

本模块包含用于解析 Minecraft 崩溃日志、可视化与辅助诊断的窗口应用逻辑。
仅对注释、日志与文档字符串进行风格化润色，保持现有行为不变。
"""

import os
import re
import threading
import webbrowser
import json
import csv
import sys
from typing import List

from config.constants import LAB_HEAD_READ_SIZE, LAB_SAMPLE_SIZE

# 确保模块可以被导入
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# 允许从 mca_core 所在目录运行脚本（将父目录加入路径）
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
try:
    root_abs = os.path.abspath(ROOT_DIR)
    if not sys.path or os.path.abspath(str(sys.path[0])) != root_abs:
        if root_abs not in map(lambda p: os.path.abspath(str(p)), sys.path):
            sys.path.insert(0, root_abs)
except Exception:
    # 容错：路径异常时不阻塞启动
    pass

# Brain System 已作为模块整合在根目录下
BRAIN_SYSTEM_DIR = ROOT_DIR

try:
    from brain_system.core import BrainCore
    HAS_BRAIN = True
except ImportError:
    HAS_BRAIN = False
    BrainCore = None

# Torch dependency removed from core to enable slimming.
# GPU detection is now handled by BrainDLCs or optional modules.
HAS_TORCH = False
torch = None

from mca_core.module_loader import ModuleLoader
from mca_core.learning import CrashPatternLearner
from mca_core.di import DIContainer
from mca_core.events import EventBus, AnalysisEvent, EventTypes
from mca_core.progress import ProgressReporter
from mca_core.task_executor import TaskExecutor
from mca_core.security import InputSanitizer
from mca_core.errors import TaskCancelledError
from config.app_config import AppConfig
from mca_core.streaming import StreamingLogAnalyzer
from mca_core.file_io import read_text_limited, read_text_head, DEFAULT_MAX_BYTES
from mca_core.ui_mixins import AnalysisEventMixin
from mca_core.settings_mixins import SettingsMixin
from mca_core.lab_mixins import LabMixin
from mca_core.plugins import PluginRegistry
from mca_core.python_runtime_optimizer import apply_version_specific_optimizations, MODE_DESCRIPTIONS
from mca_core.diagnostic_engine import DiagnosticEngine
from mca_core.crash_patterns import CrashPatternLibrary
from mca_core.dependency_analyzer import DependencyAnalyzer


try:
    from tools.generate_mc_log import generate_batch, SCENARIOS, parse_size
    HAS_LOG_GENERATOR = True
except Exception:
    generate_batch = None
    SCENARIOS = {}
    parse_size = None
    HAS_LOG_GENERATOR = False

# 核心模块（模块化管道 / 文件 I/O / 插件）

from mca_core.detectors import (
    DetectorRegistry, AnalysisContext
)
from mca_core.regex_cache import RegexCache


try:
    import psutil
    HAS_PSUTIL = True
except Exception:
    psutil = None
    HAS_PSUTIL = False

try:
    import GPUtil
    HAS_GPU_UTIL = True
except Exception:
    GPUtil = None
    HAS_GPU_UTIL = False

import traceback
from collections import defaultdict, Counter
from datetime import datetime

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import time
import logging
# 可选：TOML 解析（在 py3.11+ 上使用 tomllib，tomli 作为回退）
try:
    import tomllib as toml
    HAS_TOML = True
except Exception:
    try:
        import tomli as toml
        HAS_TOML = True
    except Exception:
        toml = None
        HAS_TOML = False

# 可选：用于事件驱动 tail 的 watchdog
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except Exception:
    HAS_WATCHDOG = False

# 可选依赖，按存在性降级处理
try:
    from tkinterweb import HtmlFrame  # 用于内嵌浏览器（若可用）
    HAS_HTMLFRAME = True
except Exception:
    HAS_HTMLFRAME = False

try:
    import networkx as nx
    import matplotlib
    # 使用 TkAgg 后端以兼容 FigureCanvasTkAgg（在有桌面/GUI 的环境下）
    try:
        matplotlib.use("TkAgg")
    except Exception:
        # 回退到 Agg 以防没有 GUI 环境
        matplotlib.use("Agg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import matplotlib.pyplot as plt
    
    # 配置字体以支持中文显示
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'sans-serif']
    plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示为方块的问题
    
    HAS_NETWORKX = True
except Exception:
    HAS_NETWORKX = False

try:
    from packaging import version as packaging_version
    HAS_PACKAGING = True
except Exception:
    HAS_PACKAGING = False

# logging 初始化
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger(__name__)
# RotatingFileHandler will be attached after BASE_DIR is defined

try:
    import openpyxl
    from openpyxl import Workbook
    HAS_OPENPYXL = True
except Exception:
    HAS_OPENPYXL = False

from config.constants import (
    WINDOW_TITLE,
    WINDOW_DEFAULT_SIZE,
    WINDOW_MIN_WIDTH,
    WINDOW_MIN_HEIGHT,
    BASE_DIR,
    HIGHLIGHT_SIZE_LIMIT,
    CAUSE_MEM,
    CAUSE_DEP,
    CAUSE_VER,
    CAUSE_DUP,
    CAUSE_GPU,
    CAUSE_GECKO,
    CAUSE_OTHER,
    GRAPH_NODE_LIMIT,
    DEFAULT_SCROLL_SENSITIVITY,
    HISTORY_FILE,
    DEPENDENCY_FILE,
    MOD_DB_FILE,
    LOADER_DB_FILE,
    MOD_CONFLICTS_FILE,
    CONFIG_FILE,
    GPU_ISSUES_FILE,
    RE_JAR_NAME_VER,
    RE_NAME_MODID_VER,
    RE_MODID_AT_VER,
    RE_CTX_DEP,
    RE_MOD_FALLBACK,
    RE_DEP_REQUESTED,
    RE_DEP_REQUIRES,
    RE_REQUESTED_BY,
)
from utils.helpers import mca_clean_modid, mca_normalize_modid, mca_levenshtein


# 辅助函数已移至 utils.helpers

import hashlib

try:
    from mca_core.idle_trainer import IdleTrainer
    HAS_IDLE_TRAINER = True
except Exception:
    HAS_IDLE_TRAINER = False

class MinecraftCrashAnalyzer(AnalysisEventMixin, SettingsMixin, LabMixin):
    def __init__(self, root: tk.Tk):
        # 根据 Python 版本应用运行时优化
        apply_version_specific_optimizations()

        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry(WINDOW_DEFAULT_SIZE)
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        # 状态变量
        self.lock = threading.RLock()       # 并发控制锁 (使用 RLock 避免 AnalysisContext 的递归锁定死锁)
        self.crash_log = ""               # 当前载入的崩溃日志文本
        self.file_path = ""               # 日志文件路径
        self.file_checksum = None         # 当前文件SHA256，用于缓存键
        self._analysis_cache = {}         # 内存缓存：校验和 -> 结果字典
        self.analysis_results = []         # 分析输出条目列表
        self.mods = defaultdict(set)       # mod_id -> set(versions)

        self.mod_names = {}                # mod_id -> display name
        self.dependency_pairs = set()      # tuples (mod, depends_on)
        self.loader_type = None            # "forge" | "fabric" | None
        self.cause_counts = Counter()      # 崩溃原因计数
        # 状态栏文本（即使不显示也用于回调更新）
        self.status_var = tk.StringVar(value="就绪")
        # 每次鼠标滚动的文本行数（可由配置覆盖）
        self.scroll_sensitivity = DEFAULT_SCROLL_SENSITIVITY
        self.highlight_size_limit = HIGHLIGHT_SIZE_LIMIT
        # tail 跟踪线程控制
        self._tail_running = False
        self._tail_thread_obj = None
        # 存储 GL / OpenGL 相关的日志片段
        self.gl_snippets = []
        # 硬件检测与诊断结果
        self.gpu_info = {}
        self.hardware_issues = []
        # 日志缓存（避免对大文件重复 lower/splitlines）
        self._log_cache_raw = None
        self._log_cache_lower = None
        self._log_cache_lines = None
        self._log_cache_lower_lines = None

        # 依赖注入容器与模块加载器
        self.container = DIContainer()
        self.module_loader = ModuleLoader(SCRIPT_DIR)
        # 标记模块可用性为实例属性，供引擎使用
        self.HAS_NEW_MODULES = False


        # 模块化管道
        self.plugin_registry = PluginRegistry()
        try:
            plugin_dir = os.path.join(os.path.dirname(SCRIPT_DIR), "plugins")
            self.plugin_registry.load_from_directory(plugin_dir)
        except Exception as e:
            logging.warning(f"加载插件失败: {e}")
        
        # 检测器配置
        self.detector_registry = DetectorRegistry()
        
        # 初始化 crash_pattern_learner (移动到 setup detectors 之前)
        try:
            pattern_path = os.path.join(BASE_DIR, "analysis_data", "learned_patterns.json")
            self.crash_pattern_learner = CrashPatternLearner(pattern_path)
        except Exception:
            self.crash_pattern_learner = None

        self._setup_detectors()

        # 初始化 Brain Core 算力引擎
        self.brain = None
        if HAS_BRAIN:
            try:
                # 尝试加载 brain_config.json (v4.1 updated location)
                brain_conf = os.path.join(BRAIN_SYSTEM_DIR, "config", "brain_config.json")
                if not os.path.exists(brain_conf):
                    # Fallback to checking root if config subdir fails (migration support)
                    brain_conf_legacy = os.path.join(BRAIN_SYSTEM_DIR, "brain_config.json")
                    if os.path.exists(brain_conf_legacy):
                        brain_conf = brain_conf_legacy
                    else:
                        brain_conf = None
                
                self.brain = BrainCore(config_path=brain_conf)
                logger.info("Brain System 算力核心初始化成功")

                # 延迟 AI 初始化，避免启动阶段卡死
                self._ai_init_started = False
                self._ai_init_lock = threading.Lock()

            except Exception as e:
                logger.warning(f"Brain System 初始化失败，将回退到默认线程池: {e}")
                self.brain = None

    def _load_dlcs_async(self):
        """后台异步加载算力 DLC."""
        if not self.brain:
            return
            
        logger.info("Starting background AI initialization...")
        # UI 更新：初始化中，启动呼吸动画
        if hasattr(self, 'ai_status_var'):
            self.root.after(0, lambda: self.ai_status_var.set("AI: Loading..."))
            self.root.after(0, self._animate_ai_loading)
        
        # 尝试加载算力相关 DLC（按依赖顺序）
        try:
            try:
                from brain_system.dlcs.brain_dlc_hardware import HardwareAcceleratorDLC
            except ImportError:
                from dlcs.brain_dlc_hardware import HardwareAcceleratorDLC

            hw_dlc = HardwareAcceleratorDLC(self.brain)
            self.brain.register_dlc(hw_dlc)
            logger.info("Hardware Accelerator DLC 已挂载")
        except Exception as dlc_error:
            logger.warning(f"Hardware Accelerator DLC 加载跳过: {dlc_error}")

        # 尝试加载 CodeBERT 语义引擎
        try:
            from dlcs.brain_dlc_codebert import CodeBertDLC
            bert_dlc = CodeBertDLC(self.brain)
            # 只有当环境满足时才挂载 (会抛出 ImportError 如果没有 transformer)
            self.brain.register_dlc(bert_dlc)
            logger.info("Semantic Engine (CodeBERT) DLC 已挂载")
            
            # 注入到学习引擎
            if self.crash_pattern_learner and bert_dlc.provide_computational_units()["is_ready"]():
                units = bert_dlc.provide_computational_units()
                self.crash_pattern_learner.set_semantic_engine(
                    units["encode_text"], 
                    units["calculate_similarity"]
                )
                logger.info("智能学习引擎已升级为：深度语义理解模式")
                if hasattr(self, 'ai_status_var'):
                    self.root.after(0, lambda: self._set_ai_ready("AI: 深度语义模型已就绪"))
        except ImportError as e:
            logger.warning(f"CodeBERT 引擎未启用 (ImportError): {e}")
            if hasattr(self, 'ai_status_var'):
                self.root.after(0, lambda: self._set_ai_ready("AI: 仅正则模式", color="#e67e22"))
        except Exception as dlc_error:
            logger.warning(f"Semantic Engine DLC 加载跳过: {dlc_error}")
            if hasattr(self, 'ai_status_var'):
                self.root.after(0, lambda: self._set_ai_ready("AI: 模型加载失败", color="#e74c3c"))

        try:
            try:
                from brain_system.dlcs.brain_dlc_nn import NeuralNetworkOperatorsDLC
            except ImportError:
                from dlcs.brain_dlc_nn import NeuralNetworkOperatorsDLC

            nn_dlc = NeuralNetworkOperatorsDLC(self.brain)
            self.brain.register_dlc(nn_dlc)
            logger.info("Neural Network Operators DLC 已挂载")
        except Exception as dlc_error:
            logger.warning(f"Neural Network Operators DLC 加载跳过: {dlc_error}")

        try:
            try:
                from brain_system.dlcs.brain_dlc_workflow import NeuralWorkflowDLC
            except ImportError:
                from dlcs.brain_dlc_workflow import NeuralWorkflowDLC

            wf_dlc = NeuralWorkflowDLC(self.brain)
            self.brain.register_dlc(wf_dlc)
            logger.info("Neural Workflow Manager DLC 已挂载")
        except Exception as dlc_error:
            logger.warning(f"Neural Workflow Manager DLC 加载跳过: {dlc_error}")

        # 最后加载分布式计算 DLC
        try:
            try:
                from brain_system.dlcs.brain_dlc_distributed import DistributedComputingDLC
            except ImportError:
                from dlcs.brain_dlc_distributed import DistributedComputingDLC
            dist_dlc = DistributedComputingDLC(self.brain)
            self.brain.register_dlc(dist_dlc)
            # 启动 Worker (使用默认配置)
            dist_dlc.start_workers(num_workers=max(2, os.cpu_count() or 2))
            logger.info("Distributed Computing DLC 已挂载")
        except Exception as dlc_error:
            logger.warning(f"分布式计算 DLC 加载跳过: {dlc_error}")

    def _start_ai_init_if_needed(self):
        if not self.brain:
            return
        if getattr(self, "_ai_init_started", False):
            return
        lock = getattr(self, "_ai_init_lock", None)
        if lock:
            with lock:
                if self._ai_init_started:
                    return
                self._ai_init_started = True
        else:
            self._ai_init_started = True

        try:
            if hasattr(self, 'ai_status_var'):
                self.ai_status_var.set("AI: 初始化中...")
        except Exception:
            pass

        threading.Thread(target=self._load_dlcs_async, daemon=True).start()

    def _setup_detectors(self):
        """注册所有可用的检测器 (DLC Mode)"""
        # 使用新的自动发现机制，不再硬编码检测器类
        self.detector_registry.load_builtins()
        
        # Self-Check: 确保核心检测器已加载 (防止打包丢失)
        loaded_count = len(self.detector_registry.list())
        if loaded_count == 0:
            import tkinter.messagebox as msgbox
            msgbox.showwarning(
                "核心组件缺失", 
                "未检测到任何故障诊断器 (Detectors)！\n\n"
                "这可能是因为程序文件损坏，或打包时配置遗漏 (Missing Hidden Imports)。\n"
                "程序将无法诊断崩溃原因。"
            )
        
        # Idle Trainer hook
        self.idle_trainer = None
        if HAS_IDLE_TRAINER:
            self.idle_trainer = IdleTrainer(self.crash_pattern_learner, os.path.join(BASE_DIR, "analysis_data", "auto_tests_idle"))
            self.idle_trainer.start()

        # 读取持久化配置（可能覆盖 scroll_sensitivity）
        try:
            self._load_config()
        except OSError:
            logger.error("加载配置失败")

        # 为持久化日志附加 rotating file handler
        try:
            from logging.handlers import RotatingFileHandler
            log_path = os.path.join(BASE_DIR, 'app.log')
            # 避免在已存在时附加多个 rotating handler
            existing = any(isinstance(h, RotatingFileHandler) and getattr(h, 'baseFilename', None) == os.path.abspath(log_path) for h in logger.handlers)
            if not existing:
                rh = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=5, encoding='utf-8')
                rh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
                logger.addHandler(rh)
        except Exception:
            logger.debug('无法创建 RotatingFileHandler，已禁用文件日志')

        # 加载本地的轻量级数据库与冲突映射
        self._ensure_db_files()
        self._load_conflict_db()

        # 初始化智能学习引擎
        try:
            from mca_core.learning import CrashPatternLearner
            storage_path = os.path.join(BASE_DIR, "analysis_data", "learned_patterns.json")
            self.crash_pattern_learner = CrashPatternLearner(storage_path)
        except Exception as e:
            logger.warning(f"无法初始化智能学习引擎: {e}")
            self.crash_pattern_learner = None

        # Initialize diagnostic engines
        self.diagnostic_engine = None
        self.crash_pattern_lib = None
        self.dependency_analyzer_cls = None
        try:
             self.diagnostic_engine = DiagnosticEngine(BASE_DIR)
             self.crash_pattern_lib = CrashPatternLibrary()
             self.dependency_analyzer_cls = DependencyAnalyzer
             self.HAS_NEW_MODULES = True
        except Exception as e:
            logger.warning(f"加载诊断模块失败: {e}")
            self.HAS_NEW_MODULES = False

        if self.diagnostic_engine:
            self.container.register_instance("DiagnosticEngine", self.diagnostic_engine)
        if self.crash_pattern_lib:
            self.container.register_instance("CrashPatternLibrary", self.crash_pattern_lib)

        # layout
        self._create_menu()
        self._create_main_panes()
        self._create_top_controls()
        self._create_log_area()
        self._create_bottom_notebook()

        # event bus / progress
        self.event_bus = EventBus()
        self.progress_reporter = ProgressReporter()
        self.task_executor = TaskExecutor()
        self.event_bus.subscribe(EventTypes.ANALYSIS_START, self._on_analysis_start_event)
        self.event_bus.subscribe(EventTypes.ANALYSIS_COMPLETE, self._on_analysis_complete_event)
        self.event_bus.subscribe(EventTypes.ANALYSIS_ERROR, self._on_analysis_error_event)
        self.event_bus.subscribe(EventTypes.ANALYSIS_PROGRESS, self._on_analysis_progress_event)
        self.event_bus.subscribe(EventTypes.DETECTOR_COMPLETE, self._on_detector_complete_event)
        self.progress_reporter.subscribe(self._on_progress_report)

        # center & style
        self._center_window()
        self._apply_styles()

        # graph lazy rendering state
        self._graph_cache_key = None
        self._graph_rendered = False
        self._cancel_event = threading.Event()
        try:
            self.bottom_notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        except Exception as e:
            logger.debug(f"绑定标签页切换事件失败: {e}")
            
        # Bind window close for cleanup
        self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)

    # ---------- cleanup ----------
    def on_window_close(self):
        """Cleanup resources on exit."""
        # 立即销毁窗口，保证UI响应
        try:
            self.root.destroy()
        except Exception:
            pass

        def _cleanup_task():
            try:
                if self.brain:
                    logger.info("正在关闭 Brain System 资源...")
                    # 停止分布式 DLC Worker (设置短超时)
                    for dlc in self.brain.dlcs.values():
                        if hasattr(dlc, "shutdown"):
                            try:
                                # Run shutdown in a thread with timeout to strictly prevent hang
                                dlc_thread = threading.Thread(target=dlc.shutdown)
                                dlc_thread.start()
                                dlc_thread.join(timeout=1.0)
                            except Exception:
                                pass
                    
                    # 关闭线程池
                    if self.brain.thread_pool:
                        self.brain.thread_pool.shutdown(wait=False)
                    if self.brain.process_pool:
                        self.brain.process_pool.shutdown(wait=False)
            except Exception as e:
                logger.error(f"清理资源失败: {e}")
            finally:
                # 强制退出，防止残留的非 daemon 线程（如 ProcessPoolExecutor 的队列线程）阻止进程结束
                # 等待 200ms 给 logger 有机会写入文件
                time.sleep(0.2)
                os._exit(0)

        # 启动后台清理线程
        t = threading.Thread(target=_cleanup_task, daemon=True)
        t.start()

    # ---------- init / helpers ----------
    def _ensure_db_files(self):
        for p in (MOD_DB_FILE, LOADER_DB_FILE, MOD_CONFLICTS_FILE, GPU_ISSUES_FILE):
            if not os.path.exists(p):
                try:
                    # write a default conflicts file if missing
                    if p == MOD_CONFLICTS_FILE:
                        default = {
                            "blacklist": [
                                {
                                    "render": ["iris", "sodium", "optifine"],
                                    "world": ["twilightforest", "twilight-forest", "thetwilightforest"],
                                    "note": "Iris/Sodium/OptiFine 与 Twilight Forest 在部分版本存在渲染钩子或 GL 初始化冲突，建议移除光影或使用兼容补丁/特定版本。"
                                },
                                {
                                    "render": ["iris"],
                                    "world": ["betterend", "byg"],
                                    "note": "Iris 与 某些世界类MOD 在 Forge 环境下曾报告兼容性问题，按需排查。"
                                }
                            ],
                            "whitelist": [
                                {
                                    "render": ["indium"],
                                    "world": ["twilightforest"],
                                    "note": "Indium 在部分情况下与 Twilight Forest 有更好兼容性（视版本而定）。"
                                }
                            ]
                        }
                        with open(p, "w", encoding="utf-8") as f:
                            json.dump(default, f, ensure_ascii=False, indent=2)
                        continue
                    # 初始化 GPU 问题数据库为示例条目
                    if p == GPU_ISSUES_FILE:
                        gpu_default = {
                            "rules": [
                                {"vendor": "nvidia", "match": ["nvidia", "geforce"], "advice": "更新 NVIDIA 驱动到最新稳定版；尝试回退若最新驱动有问题；禁用光影或使用 Indium 替代 Iris。"},
                                {"vendor": "intel", "match": ["intel", "iris graphics"], "advice": "更新 Intel GPU 驱动；对集成显卡，降低渲染设置并禁用光影。"},
                                {"vendor": "amd", "match": ["amd", "radeon"], "advice": "更新 AMD 驱动；尝试使用兼容的着色器/渲染器组合。"}
                            ]
                        }
                        with open(p, "w", encoding="utf-8") as f:
                            json.dump(gpu_default, f, ensure_ascii=False, indent=2)
                        continue
                    with open(p, "w", encoding="utf-8") as f:
                        json.dump({}, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    logger.error(f"无法创建默认数据库文件 {p}: {e}")
        # 尝试加载 GPU issues 到内存（容错）
        try:
            self._load_gpu_issues()
        except Exception:
            self.gpu_issues = {}
            logger.warning("GPU数据库加载失败，将使用空集合")

    def _load_gpu_issues(self):
        try:
            if os.path.exists(GPU_ISSUES_FILE):
                with open(GPU_ISSUES_FILE, "r", encoding="utf-8") as f:
                    self.gpu_issues = json.load(f)
            else:
                self.gpu_issues = {}
        except Exception as e:
            logger.exception("无法加载 GPU issues 文件: %s", e)
            self.gpu_issues = {}

    def _load_config(self):
        try:
            self.app_config = AppConfig.load(CONFIG_FILE)
            if isinstance(self.app_config.scroll_sensitivity, int) and self.app_config.scroll_sensitivity > 0:
                self.scroll_sensitivity = self.app_config.scroll_sensitivity
            if isinstance(self.app_config.highlight_size_limit, int) and self.app_config.highlight_size_limit > 0:
                self.highlight_size_limit = self.app_config.highlight_size_limit
        except Exception:
            logger.exception("加载配置失败")

    def _save_config(self):
        try:
            if not getattr(self, "app_config", None):
                self.app_config = AppConfig()
            self.app_config.scroll_sensitivity = int(self.scroll_sensitivity)
            self.app_config.highlight_size_limit = int(self.highlight_size_limit)
            self.app_config.save(CONFIG_FILE)
        except Exception:
            logger.exception("保存配置失败")

    def _reload_config_if_changed(self):
        try:
            if getattr(self, "app_config", None):
                self.app_config = self.app_config.reload_if_changed(CONFIG_FILE)
                if isinstance(self.app_config.scroll_sensitivity, int) and self.app_config.scroll_sensitivity > 0:
                    self.scroll_sensitivity = self.app_config.scroll_sensitivity
                if isinstance(self.app_config.highlight_size_limit, int) and self.app_config.highlight_size_limit > 0:
                    self.highlight_size_limit = self.app_config.highlight_size_limit
        except Exception as e:
            logger.debug(f"配置热重载失败: {e}")

    # ---------- log cache helpers ----------
    def _invalidate_log_cache(self):
        self._log_cache_raw = None
        self._log_cache_lower = None
        self._log_cache_lines = None
        self._log_cache_lower_lines = None

    def _ensure_log_cache(self):
        if self._log_cache_raw is not self.crash_log:
            self._log_cache_raw = self.crash_log
            self._log_cache_lower = None
            self._log_cache_lines = None
            self._log_cache_lower_lines = None

    def _get_log_text(self):
        return self.crash_log or ""

    def _get_log_lower(self):
        self._ensure_log_cache()
        if self._log_cache_lower is None:
            self._log_cache_lower = (self.crash_log or "").lower()
        return self._log_cache_lower

    def _get_log_lines(self, lower=False):
        self._ensure_log_cache()
        if lower:
            if self._log_cache_lower_lines is None:
                self._log_cache_lower_lines = self._get_log_lower().splitlines()
            return self._log_cache_lower_lines
        if self._log_cache_lines is None:
            self._log_cache_lines = (self.crash_log or "").splitlines()
        return self._log_cache_lines

    def _suggest_dependency_install(self):
        """检测并记录可选依赖缺失的友好提示。

        不强制安装，仅在日志与状态栏提供安装建议，便于用户按需补装。
        """
        missing = []
        if not HAS_NETWORKX:
            missing.append("networkx matplotlib")
        if not HAS_HTMLFRAME:
            missing.append("tkinterweb (可选)")
        if missing:
            # 给出简洁的安装提示（包名可能包含空格或说明，取第一个词作为示例）
            example_pkgs = ' '.join(p.split()[0] for p in missing)
            msg = f"检测到可选依赖缺失: {', '.join(missing)}。可使用 pip 安装，例如: pip install {example_pkgs}"
            logger.info(msg)
            try:
                if hasattr(self, 'status_var'):
                    self.status_var.set("检测到可选依赖，详情请查看日志")
            except Exception:
                logger.debug("设置 status_var 时发生错误，忽略")

    def _collect_system_info(self):
        """收集系统与运行时环境信息。

        输出包含平台、Python 版本以及在可用时由 psutil/GPUtil 提供的 CPU、内存与 GPU 信息。
        在可选依赖缺失时，函数会尽可能退回到基础信息而不抛出异常。
        """
        info = {}
        try:
            import platform
            info['platform'] = platform.platform()
            info['python'] = platform.python_version()
            try:
                import psutil
                info['cpu_count'] = psutil.cpu_count(logical=False)
                info['memory_total'] = getattr(psutil.virtual_memory(), 'total', None)
            except Exception:
                logger.debug("psutil 未安装或获取系统信息失败")
            try:
                import GPUtil
                gpus = GPUtil.getGPUs()
                info['gpus'] = [{ 'name': g.name, 'driver': getattr(g, 'driver', None), 'memoryTotal': getattr(g, 'memoryTotal', None) } for g in gpus]
            except Exception:
                logger.debug("GPUtil 未安装或无法获取 GPU 信息")
        except Exception:
            logger.exception("收集系统信息失败")
        return info

    def _clean_modid(self, raw: str):
        """委托到模块级别实现"""
        return mca_clean_modid(raw)

    def _normalize_modid(self, name: str):
        """尝试将任意展示名/文本映射到已识别的 modid 集合中，使用大小写无关匹配+编辑距离模糊匹配。"""
        return mca_normalize_modid(name, self.mods.keys(), self.mod_names)

    def _load_conflict_db(self):
        """载入 `mod_conflicts.json` 到 `self.conflict_db`。

        若文件不可用或解析失败，回退到默认的空结构。载入后将相关匹配项规范化为小写以便快速匹配。
        """
        try:
            with open(MOD_CONFLICTS_FILE, "r", encoding="utf-8") as f:
                self.conflict_db = json.load(f)
        except Exception:
            self.conflict_db = {"blacklist": [], "whitelist": []}
        # 规范化小写版本以便匹配
        for section in ("blacklist", "whitelist"):
            items = self.conflict_db.get(section) or []
            for it in items:
                it["render"] = [r.lower() for r in it.get("render", [])]
                it["world"] = [w.lower() for w in it.get("world", [])]

    def _center_window(self):
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"+{x}+{y}")

    def _apply_styles(self):
        try:
            import sv_ttk
            theme = getattr(getattr(self, "app_config", None), "theme", "light")
            sv_ttk.set_theme(theme)
        except Exception as e:
            logger.warning(f"无法应用 UI 主题: {e}")

    # ---------- UI creation ----------
    def _create_menu(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="打开日志文件...", command=self.load_file)
        file_menu.add_command(label="导入 Mods 列表...", command=self.import_mods)
        file_menu.add_command(label="清除", command=self.clear_content)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)
        menubar.add_cascade(label="文件", menu=file_menu)

        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="导出依赖关系图谱", command=self.export_dependencies)
        tools_menu.add_command(label="导出分析报告 (HTML/TXT)", command=self.export_analysis_report)
        tools_menu.add_command(label="查看分析历史", command=self.view_history)
        tools_menu.add_separator()
        tools_menu.add_command(label="启动 AI 引擎", command=self._start_ai_init_if_needed)
        tools_menu.add_separator()
        
        # Log Controls moved from Toolbar
        tools_menu.add_command(label="开启/停止日志实时跟踪 (Tail)", command=self._toggle_tail)
        
        tools_menu.add_separator()
        # Neural Tools
        neural_menu = tk.Menu(tools_menu, tearoff=0)
        neural_menu.add_command(label="启动对抗生成器 (CLI)", command=self._launch_adversarial_gen)
        neural_menu.add_command(label="GPU 环境配置向导", command=self._launch_gpu_setup)
        tools_menu.add_cascade(label="神经对抗工具箱 (Neural Tools)", menu=neural_menu)
        
        menubar.add_cascade(label="工具", menu=tools_menu)
        
        # View Menu for Settings
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="重置窗口布局", command=self._apply_styles) # Dummy reset
        
        # Slider submenu
        sens_menu = tk.Menu(view_menu, tearoff=0)
        for val in [1, 3, 5, 10, 20]:
            sens_menu.add_radiobutton(label=f"速度 {val}x", value=val, variable=self.sens_var if hasattr(self, 'sens_var') else tk.IntVar(value=self.scroll_sensitivity), command=lambda v=val: self._set_sensitivity(v))
        view_menu.add_cascade(label="滚动灵敏度", menu=sens_menu)
        
        menubar.add_cascade(label="视图", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="在线解决方案", command=self.setup_solution_browser)
        help_menu.add_command(label="关于", command=self.open_help)
        menubar.add_cascade(label="帮助", menu=help_menu)

        self.root.config(menu=menubar)

    def _set_sensitivity(self, val):
        self.scroll_sensitivity = val
        if hasattr(self, 'sens_var'):
            self.sens_var.set(val)


    def _launch_adversarial_gen(self):
        """Launching the adversarial generator in a new console."""
        try:
            script_path = os.path.join(ROOT_DIR, "tools", "generate_mc_log.py")
            if os.name == 'nt':
                 # Use start to open in a new cmd window
                 os.system(f'start cmd /k "{sys.executable} {script_path} --help"')
            else:
                 messagebox.showinfo("提示", "请在终端运行: python tools/generate_mc_log.py")
        except Exception as e:
            messagebox.showerror("启动失败", str(e))

    def _launch_gpu_setup(self):
        """Launching the GPU setup tool."""
        try:
            script_path = os.path.join(ROOT_DIR, "tools", "gpu_setup.py")
            if os.name == 'nt':
                 os.system(f'start cmd /k "{sys.executable} {script_path}"')
            else:
                 messagebox.showinfo("提示", "请在终端运行: python tools/gpu_setup.py")
        except Exception as e:
            messagebox.showerror("启动失败", str(e))

    def open_help(self):
        messagebox.showinfo("关于", "Minecraft Crash Analyzer (v1.0 - Brain System)\n\n"
                                    "Powered by BrainCore Architecture.\n"
                                    "Supports Modular DLCs & Hotfix Patches.\n"
                                    "First Public Release 2026.")


    def _create_main_panes(self):
        # 主内容区 Frame，作为其它控件的容器
        self.scrollable_frame = ttk.Frame(self.root)
        self.scrollable_frame.pack(fill="both", expand=True)

        # 全局滚轮绑定到根窗口，文本控件进入时会获取焦点以优先处理滚轮
        try:
            self.root.bind_all("<MouseWheel>", self._on_mousewheel)
            self.root.bind_all("<Button-4>", self._on_mousewheel)
            self.root.bind_all("<Button-5>", self._on_mousewheel)
        except Exception as e:
            logger.exception("绑定鼠标滚轮失败: %s", e)

    def _on_mousewheel(self, event):
        """统一处理鼠标滚轮。"""
        try:
            # 1. 优先检测是否在 ScrolledText 等可滚动区域内
            # 如果不这样 check，容易导致在无关区域滚动时报错或不响应
            widget = event.widget
            
            # 向上查找直到找到 Text 或 Canvas 这样的可滚动实体，或者到达顶层
            target_scrollable = None
            curr = widget
            while curr and curr != self.root:
                if hasattr(curr, "yview") and (isinstance(curr, (tk.Text, tk.Canvas, tk.Listbox)) or "scrolledtext" in str(type(curr))):
                    target_scrollable = curr
                    break
                # 处理 ttk.Treeview
                if hasattr(curr, "yview") and "Treeview" in str(type(curr)):
                    target_scrollable = curr
                    break
                curr = getattr(curr, "master", None)

            # 如果找到了具体的可滚动子控件（如日志框、结果框），优先滚动它
            if target_scrollable:
                delta = getattr(event, "delta", 0)
                num = getattr(event, "num", 0)
                
                # 计算步长
                step = 0
                if delta:
                    step = int(-1 * (delta / 120))
                elif num == 4:
                    step = -1
                elif num == 5:
                    step = 1
                
                if step != 0:
                    try:
                        target_scrollable.yview_scroll(step * getattr(self, 'scroll_sensitivity', 1), "units")
                    except Exception: 
                        pass # 忽略部分控件不支持 sub-unit scroll
                return "break" # 阻止事件传播，防止外层画布也跟着滚

            # 2. 如果没有在特定子控件内，则滚动主画布
            # (已移除这部分逻辑，因为外层使用了 ttk.Frame + pack，可能不再需要 Canvas 滚动，或者由 Text 撑满)
            # 如果确实有外层 Canvas，可以在这里处理
            return 
        except Exception as e:
            # logger.debug("_on_mousewheel error: %s", e)
            pass

    def _create_top_controls(self):
        # Initial sensitivity var for menu binding
        if not hasattr(self, 'sens_var'):
            self.sens_var = tk.IntVar(value=self.scroll_sensitivity)

        top_frame = ttk.Frame(self.scrollable_frame, padding=12)
        top_frame.pack(fill="x", padx=10, pady=(5, 0))
        
        # New simplified Toolbar Design with Big Buttons
        # [ ICON | Open Log ] [ ICON | Start Analysis ] ...
        
        # Left Side: Primary Actions
        btn_style = "Accent.TButton" # Try to use accented button if theme supports it
        
        # 1. Open Log
        open_btn = ttk.Button(top_frame, text="📂 打开日志", command=self.load_file, width=15)
        open_btn.pack(side="left", padx=5)

        # 2. Start Analysis (Primary)
        # We can simulate primary style if Accent.TButton isn't defined by just placement
        analyze_btn = ttk.Button(top_frame, text="▶ 开始分析", command=self.start_analysis, width=15)
        analyze_btn.pack(side="left", padx=5)

        # 3. Clear text
        clear_btn = ttk.Button(top_frame, text="🗑️ 清除", command=self.clear_content, width=10)
        clear_btn.pack(side="left", padx=5)

        # Separator (Vertical)
        ttk.Separator(top_frame, orient="vertical").pack(side="left", fill="y", padx=10, pady=2)
        
        # Info Label (replacing cluttered buttons)
        self.status_hint = ttk.Label(top_frame, text="请加载日志文件...", foreground="#7f8c8d", font=("Segoe UI", 9))
        self.status_hint.pack(side="left", padx=5)


        # Right Side: Status Monitors

        # 2. 脑机接口状态监视器 (Brain Status Monitor)
        # 布局: [AI Canvas] --neck-- [System Status]
        
        status_container = ttk.Frame(top_frame)
        status_container.pack(side="right", padx=6)

        # GPU Indicator (Neural Core)
        gpu_status_text = "N/A"
        gpu_color = "#95a5a6" # Grey
        
        # Dynamic check for Torch (in case loaded by DLCs)
        runtime_torch = sys.modules.get("torch")
        
        if runtime_torch and hasattr(runtime_torch, "cuda") and runtime_torch.cuda.is_available():
            try:
                gpu_name = runtime_torch.cuda.get_device_name(0)
                if "RTX 50" in gpu_name or "GB2" in gpu_name: # 50 series or Blackwell architecture
                     gpu_status_text = "CUDA 13 (RTX 50)"
                     gpu_color = "#2ecc71" # Bright Green
                else:
                     gpu_status_text = "CUDA ON"
                     gpu_color = "#27ae60"
            except Exception:
                gpu_status_text = "CUDA ERR"
        elif runtime_torch:
             gpu_status_text = "CPU (Torch)"
             gpu_color = "#f39c12" # Orange
        else:
             gpu_status_text = "STANDARD (Lite)"
             gpu_color = "#3498db" # Blue
        
        # Wrap status in a nice frame or label pair
        gpu_frame = ttk.Frame(status_container)
        gpu_frame.pack(side="right", padx=5)
        
        ttk.Label(gpu_frame, text="CORE:", font=("Segoe UI", 7)).pack(side="left", padx=0)
        gpu_lbl = ttk.Label(gpu_frame, text=gpu_status_text, foreground=gpu_color, font=("Segoe UI", 9, "bold"))
        gpu_lbl.pack(side="left", padx=2)

        # Brain (Canvas)
        # Fix: ttk.Frame doesn't support .cget("background") on all themes, use style lookup or default
        brain_bg = "#f0f0f0" # Default fallback
        try:
             style_bg = ttk.Style().lookup("TFrame", "background")
             if style_bg:
                 brain_bg = style_bg
        except:
             pass

        # 加宽画布防止遮挡
        self.brain_canvas = tk.Canvas(status_container, width=64, height=50, highlightthickness=0, bg=brain_bg)

        
        # 1. 脊髓基座 (Spinal Pedestal) - 机械风格
        # 底部宽基座
        self.brain_canvas.create_polygon(24, 50, 40, 50, 38, 42, 26, 42, fill="#7f8c8d", outline="", tags="spine_base_low")
        # 顶部接口台
        self.brain_canvas.create_rectangle(26, 38, 38, 42, fill="#bdc3c7", outline="", tags="spine_platform")
        
        # 2. 神经束 (Serve Cable) - 粗壮的线缆
        # 内部透光缆
        self.brain_canvas.create_line(32, 40, 32, 22, fill="#566573", width=6, tags="spine_cable_inner")
        # 外部护甲环 (装饰性短横线)
        self.brain_canvas.create_line(28, 36, 36, 36, fill="#95a5a6", width=2, tags="spine_ring_1")
        self.brain_canvas.create_line(28, 30, 36, 30, fill="#95a5a6", width=2, tags="spine_ring_2")

        # 3. 大脑皮层 (Holographic Cortex) - 扁平化设计，不再像气球
        # 绘制半透明的大脑轮廓 (扁圆)
        # 左半球
        self.brain_canvas.create_arc(10, 10, 54, 46, start=0, extent=180, outline="#bdc3c7", width=2, style="arc", tags="cortex_main")
        # 内部脑回纹理 (Gyri)
        self.brain_canvas.create_arc(18, 18, 46, 38, start=20, extent=140, outline="#d5d8dc", width=1, style="arc", tags="cortex_inner")
        
        # 4. 数据接口点 (Data Nodes)
        self.brain_canvas.create_oval(30, 20, 34, 24, fill="#ecf0f1", outline="", tags="central_node")

        # 初始化时，核心是暗的
        self.brain_canvas.pack(side="right")

        # 初始化 AI 状态变量
        if not hasattr(self, 'ai_status_var'):
            self.ai_status_var = tk.StringVar(value="AI: 待启用(手动启动)")

        self.progress = ttk.Progressbar(self.scrollable_frame, mode="indeterminate")
        self.progress.pack(fill="x", padx=10, pady=(4, 6))
        self.progress.stop()
        self.progress.pack_forget()

    def _create_log_area(self):
        # 日志区域
        log_frame = ttk.LabelFrame(self.scrollable_frame, text="崩溃日志", padding=6)
        log_frame.pack(fill="both", expand=False, padx=10, pady=(0, 10))

        self.log_text = scrolledtext.ScrolledText(log_frame, height=18, wrap="none", font=("Consolas", 10))
        self.log_text.pack(fill="both", expand=True)
    
        # 当鼠标进入日志区域时聚焦，以便滚轮事件直接由该控件处理
        try:
            self.log_text.bind("<Enter>", lambda e: self.log_text.focus_set())
        except Exception:
            pass
        # 高亮tag
        self.log_text.tag_config("highlight", background="#f39c12", foreground="black")
        self.log_text.tag_config("error", background="#e74c3c", foreground="white")
        
        # Initialize as read-only
        self.log_text.config(state="disabled")

        def _on_log_wheel(event):
            # 直接处理文本控件的滚动
            widget = event.widget
            if event.delta:
                widget.yview_scroll(-1 * (event.delta // 120) * self.scroll_sensitivity, "units")
            elif event.num == 4:
                widget.yview_scroll(-1 * self.scroll_sensitivity, "units")
            elif event.num == 5:
                widget.yview_scroll(1 * self.scroll_sensitivity, "units")
        return "break" # 阻止事件传播，防止外层画布也跟着滚

    def _redraw_brain_base(self):
        """重绘大脑的基础结构"""
        try:
            self.brain_canvas.delete("all")
            
            # 1. 脊髓基座 (Spinal Pedestal)
            self.brain_canvas.create_polygon(24, 50, 40, 50, 38, 42, 26, 42, fill="#7f8c8d", outline="", tags="spine_base_low")
            self.brain_canvas.create_rectangle(26, 38, 38, 42, fill="#bdc3c7", outline="", tags="spine_platform")
            
            # 2. 神经束 (Serve Cable)
            self.brain_canvas.create_line(32, 40, 32, 22, fill="#566573", width=6, tags="spine_cable_inner")
            self.brain_canvas.create_line(28, 36, 36, 36, fill="#95a5a6", width=2, tags="spine_ring_1")
            self.brain_canvas.create_line(28, 30, 36, 30, fill="#95a5a6", width=2, tags="spine_ring_2")

            # 3. 大脑皮层 (Holographic Cortex) - 实体化设计
            # 脑质填充 (Brain Matter Body) - 给大脑更有"分量"的感觉
            self.brain_canvas.create_oval(12, 12, 52, 44, fill="#e5e8e8", outline="", tags="brain_matter")
            
            # 外轮廓 (Main Shell)
            self.brain_canvas.create_arc(10, 8, 54, 48, start=0, extent=180, outline="#566573", width=2, style="arc", tags="cortex_main")
            
            # 脑沟回纹理 (Gyri & Sulci) - 密集化处理
            gyri_col = "#95a5a6"
            
            # 左脑半球 (Left Hemisphere)
            # 额叶
            self.brain_canvas.create_line(14, 28, 16, 22, 22, 18, 28, 20, fill=gyri_col, smooth=True, width=1, tags="cortex_gyri")
            self.brain_canvas.create_line(14, 22, 18, 16, 24, 14, fill=gyri_col, smooth=True, width=1, tags="cortex_gyri")
            # 颞叶
            self.brain_canvas.create_line(16, 34, 20, 30, 26, 28, fill=gyri_col, smooth=True, width=1, tags="cortex_gyri")
            # 内部细节
            self.brain_canvas.create_line(22, 24, 26, 20, 24, 16, fill=gyri_col, smooth=True, width=1, tags="cortex_gyri")

            # 右脑半球 (Right Hemisphere)
            # 额叶
            self.brain_canvas.create_line(50, 28, 48, 22, 42, 18, 36, 20, fill=gyri_col, smooth=True, width=1, tags="cortex_gyri")
            self.brain_canvas.create_line(50, 22, 46, 16, 40, 14, fill=gyri_col, smooth=True, width=1, tags="cortex_gyri")
            # 颞叶
            self.brain_canvas.create_line(48, 34, 44, 30, 38, 28, fill=gyri_col, smooth=True, width=1, tags="cortex_gyri")
            # 内部细节
            self.brain_canvas.create_line(42, 24, 38, 20, 40, 16, fill=gyri_col, smooth=True, width=1, tags="cortex_gyri")

            # 中缝 (Longitudinal Fissure) - 加深强调
            self.brain_canvas.create_line(32, 10, 32, 38, fill="#7f8c8d", width=1, tags="cortex_fissure")

            # 4. 数据接口点
            self.brain_canvas.create_oval(30, 20, 34, 24, fill="#ecf0f1", outline="", tags="central_node")
        except: pass

    def _animate_ai_loading(self, frame=0):
        """AI 加载状态呼吸灯动画"""
        val = self.ai_status_var.get()
        if "Loading" not in val and "初始化" not in val:
            return

        try:
            # 基础重绘 (防止残影)
            self.brain_canvas.delete("core_glow") 
            
            # 红色警报脉冲
            import math
            pulse = (math.sin(frame * 0.2) + 1) / 2 # 0~1
            
            # 线缆亮红光
            red_intensity = int(100 + 155 * pulse)
            hex_col = f"#{red_intensity:02x}0000"
            self.brain_canvas.itemconfig("spine_cable_inner", fill=hex_col)
            
            # 核心闪烁
            if frame % 10 < 5:
                self.brain_canvas.itemconfig("central_node", fill="#e74c3c")
            else:
                self.brain_canvas.itemconfig("central_node", fill="#c0392b")

            self.root.after(100, lambda: self._animate_ai_loading(frame + 1))
        except Exception:
            pass

    def _animate_ai_rotating(self, angle=0):
        """AI 就绪状态旋转动画"""
        val = self.ai_status_var.get()
        if "Loading" in val or "初始化" in val or "失败" in val or "未启用" in val:
             return
             
        try:
            # 确保基础绘图存在 (防止残影叠加)
            self.brain_canvas.delete("data_particle")
            
            # 激活状态配置 (绿色流动)
            try:
                self.brain_canvas.itemconfig("spine_cable_inner", fill="#2ecc71") 
                self.brain_canvas.itemconfig("cortex_main", outline="#58d68d")
            except: pass
            
            # 绘制数据流 (Data Flow)
            import math
            t = (angle % 20) / 20.0 
            
            # 粒子1：沿主脊髓上升 (y: 45 -> 22)
            y_up = 45 - (23 * t)
            self.brain_canvas.create_oval(31, y_up-1, 33, y_up+1, fill="#FFFFFF", outline="", tags="data_particle")
            
            # 粒子2：在皮层内扩散 (从中心向四周)
            t2 = ((angle + 10) % 20) / 20.0
            
            # 左上扩散 - x: 32->14, y: 22->14
            lx = 32 - (18 * t2)
            ly = 22 - (8 * t2)
            self.brain_canvas.create_oval(lx-1, ly-1, lx+1, ly+1, fill="#abebc6", outline="", tags="data_particle")
            
            # 右上扩散 - x: 32->50, y: 22->14
            rx = 32 + (18 * t2)
            ry = 22 - (8 * t2)
            self.brain_canvas.create_oval(rx-1, ry-1, rx+1, ry+1, fill="#abebc6", outline="", tags="data_particle")

            # 核心光晕 (Central Node Pulse)
            pulse = math.sin(math.radians(angle * 8)) * 0.3 + 0.7 
            if pulse > 0.8:
                self.brain_canvas.itemconfig("central_node", fill="#2ecc71")
            else:
                self.brain_canvas.itemconfig("central_node", fill="#27ae60")

            self.root.after(50, lambda: self._animate_ai_rotating(angle + 1))
        except Exception:
            pass

    def _set_ai_ready(self, text, color="#2ecc71"):
        """设置 AI 最终状态并启动旋转"""
        self.ai_status_var.set(text)
        try:
            if "失败" in text or "正则" in text:
                self._redraw_brain_base()
                # 灰色死机状态
                self.brain_canvas.itemconfig("spine_cable_inner", fill="#2c3e50")
                self.brain_canvas.itemconfig("central_node", fill="#ecf0f1")
            else:
                self._animate_ai_rotating(0)
        except Exception:
            pass

    def _create_bottom_notebook(self):
        bottom_frame = ttk.Frame(self.scrollable_frame)
        bottom_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.bottom_notebook = ttk.Notebook(bottom_frame)
        self.bottom_notebook.pack(fill="both", expand=True)

        # 分析结果
        self.analysis_tab = ttk.Frame(self.bottom_notebook)
        self.bottom_notebook.add(self.analysis_tab, text="分析结果")

        self.result_text = scrolledtext.ScrolledText(self.analysis_tab, state="disabled", height=12, font=("Segoe UI", 10))
        self.result_text.pack(fill="both", expand=True, padx=8, pady=8)
        
        # 配置 Tag 样式 (用于高亮 AI 建议)
        self.result_text.tag_config("ai_header", foreground="#2980b9", font=("Segoe UI", 11, "bold"))
        self.result_text.tag_config("ai_content", foreground="#2c3e50", background="#eaf2f8")
        
        try:
            self.result_text.bind("<Enter>", lambda e: self.result_text.focus_set())
        except Exception:
            pass
        # 崩溃原因占比
        self.cause_tab = ttk.Frame(self.bottom_notebook)
        self.bottom_notebook.add(self.cause_tab, text="原因占比")
        self._create_cause_tab()

        # 依赖图
        self.graph_tab = ttk.Frame(self.bottom_notebook)
        self.bottom_notebook.add(self.graph_tab, text="MOD依赖关系图")
        self.graph_frame = ttk.Frame(self.graph_tab, padding=8)
        self.graph_frame.pack(fill="both", expand=True)
        self._create_graph_controls()

        # 在线解决方案（浏览器）
        self.web_tab = ttk.Frame(self.bottom_notebook)
        self.bottom_notebook.add(self.web_tab, text="在线解决方案")
        self.setup_solution_browser(init_only=True)

    # 硬件诊断页
        self.hw_tab = ttk.Frame(self.bottom_notebook)
        self.bottom_notebook.add(self.hw_tab, text="硬件诊断")
        self._create_hw_tab()

        # 运行时优化页 (新增)
        self.opt_tab = ttk.Frame(self.bottom_notebook)
        self.bottom_notebook.add(self.opt_tab, text="运行时优化")
        self._create_opt_tab()

        # 自动化测试页 (内测/研发)
        self.auto_test_tab = ttk.Frame(self.bottom_notebook)
        self.bottom_notebook.add(self.auto_test_tab, text="自动化测试")
        self._create_auto_test_tab()

    def _create_graph_controls(self):
        ctrl = ttk.Frame(self.graph_frame)
        ctrl.pack(fill="x")
        
        # 布局选择
        ttk.Label(ctrl, text="布局算法:").pack(side="left", padx=(0, 4))
        # 默认采用树形布局，便于阅读依赖链；用户可切换
        self.layout_var = tk.StringVar(value="Hierarchy (树形)")
        self.layout_combo = ttk.Combobox(ctrl, textvariable=self.layout_var, state="readonly", width=16)
        self.layout_combo['values'] = (
            "Hierarchy (树形)",
            "Spring (力导向)",
            "Circular (圆形)",
            "Shell (同心圆)",
            "Spectral (谱布局)",
            "Random (随机)"
        )
        self.layout_combo.pack(side="left", padx=4)
        self.layout_combo.bind("<<ComboboxSelected>>", lambda e: self.update_dependency_graph())

        # 过滤孤立点开关
        self.filter_isolated_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(ctrl, text="隐藏无依赖MOD", variable=self.filter_isolated_var, command=self.update_dependency_graph).pack(side="left", padx=10)

        ttk.Button(ctrl, text="保存图表", command=self.save_dependency_graph).pack(side="right", padx=6)
        ttk.Button(ctrl, text="导出依赖(CSV)", command=self.export_dependencies).pack(side="right", padx=6)
        ttk.Button(ctrl, text="查看历史", command=self.view_history).pack(side="right", padx=6)

        self.canvas_container = ttk.Frame(self.graph_frame)
        self.canvas_container.pack(fill="both", expand=True, pady=6)

    # 占位label
        self.graph_placeholder = ttk.Label(self.canvas_container, text="分析后显示依赖关系图", foreground="#666666")
        self.graph_placeholder.pack(expand=True)

    def _create_cause_tab(self):
        frame = ttk.Frame(self.cause_tab, padding=8)
        frame.pack(fill="both", expand=True)
        self.cause_canvas_container = ttk.Frame(frame)
        self.cause_canvas_container.pack(fill="both", expand=True)
        self.cause_placeholder = ttk.Label(self.cause_canvas_container, text="分析后显示崩溃原因占比", foreground="#666666")
        self.cause_placeholder.pack(expand=True)

    def open_in_external_browser(self):
        """
        统一打开当前内嵌浏览器页或在外部用必应搜索打开默认查询。
        保留单一定义，避免之前文件中出现重复定义导致覆盖或使用不一致的搜索引擎。
        """
        try:
            if hasattr(self, "browser") and self.browser:
                url = None
                try:
                    url = self.browser.get_current_url()
                except Exception:
                    try:
                        url = self.browser.get_url()
                    except Exception:
                        url = None
                if url:
                    safe_url = InputSanitizer.sanitize_url(url)
                    if safe_url:
                        webbrowser.open(safe_url)
                    return
            # fallback 使用必应
            webbrowser.open("https://www.bing.com/search?q=minecraft+crash+solutions")
        except Exception:
            webbrowser.open("https://www.bing.com/search?q=minecraft+crash+solutions")

    def _on_sens_change(self):
        try:
            val = int(self.sens_var.get())
            if val < 1:
                val = 1
            self.scroll_sensitivity = val
            self._save_config()
        except ValueError:
            # 用户可能输入了非数字，忽略并在下次自动修正
            pass
        except Exception as e:
            logger.error(f"更新滚动灵敏度失败: {e}")

    def _create_hw_tab(self):
        # 简单硬件诊断 UI：GPU 信息 / 驱动 / GL 片段
        try:
            for w in self.hw_tab.winfo_children():
                w.destroy()
        except Exception:
            pass

        top = ttk.Frame(self.hw_tab, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="硬件诊断（基于日志的启发式检测）").pack(side="left")
        ttk.Button(top, text="刷新检测", command=self._refresh_hardware_analysis).pack(side="right")

        body = ttk.Frame(self.hw_tab, padding=8)
        body.pack(fill="both", expand=True)

        self.hw_text = scrolledtext.ScrolledText(body, height=12)
        self.hw_text.pack(fill="both", expand=True)

        # GL 片段展示与复制
        ctrl = ttk.Frame(self.hw_tab)
        ctrl.pack(fill="x", pady=6)
        ttk.Button(ctrl, text="复制 GL 片段", command=self._copy_gl_snippets).pack(side="right", padx=6)







    def _create_legacy_auto_test_tab(self): # Renamed to avoid conflict with Neural Core Lab
        try:
            for w in self.auto_test_tab.winfo_children():
                w.destroy()
        except Exception:
            pass
            
        # Re-create main layout for auto test tab which seems missing in this specific block in the provided code
        # However, looking at the code around line 1493, there is already a _create_auto_test_tab. 
        # The code at line 1582 seems to be a stray method definition named _create_opt_tab re-defining logic for auto test.
        # Assuming we need to fix the one at 1582 which is causing the error.
        
        # If this is indeed the intended method for the tab content:
        main_frame = ttk.Frame(self.auto_test_tab, padding=10) # Fallback if main_frame is missing
        main_frame.pack(fill="both", expand=True)
        
        opts_frame = ttk.Frame(main_frame)
        opts_frame.pack(fill="x", pady=5)
        
        if not hasattr(self, 'auto_test_isolated_var'):
            self.auto_test_isolated_var = tk.BooleanVar(value=False)

        ttk.Checkbutton(opts_frame, text="使用隔离库", variable=self.auto_test_isolated_var).pack(side="left", padx=12)

        # === Idle Trainer Section ===
        if HAS_IDLE_TRAINER and self.idle_trainer:
            idle_frame = ttk.LabelFrame(main_frame, text="闲置后台训练服务", padding=10)
            idle_frame.pack(fill="x", padx=4, pady=(8, 8))
            
            self.idle_enable_var = tk.BooleanVar(value=self.idle_trainer.enabled)
            self.idle_duration_hours = tk.StringVar(value=str(self.idle_trainer.duration_hours))
            self.idle_cpu_limit = tk.StringVar(value=str(self.idle_trainer.max_cpu))
            self.idle_ram_limit = tk.StringVar(value=str(self.idle_trainer.max_ram))
            self.idle_gpu_limit = tk.StringVar(value=str(self.idle_trainer.max_gpu))
            self.idle_trained_cnt = tk.StringVar(value="0")
            
            def _toggle_idle():
                self.idle_trainer.enabled = self.idle_enable_var.get()
            
            def _update_idle_cfg(*args):
                try:
                    self.idle_trainer.duration_hours = float(self.idle_duration_hours.get())
                    self.idle_trainer.max_cpu = float(self.idle_cpu_limit.get())
                    self.idle_trainer.max_ram = float(self.idle_ram_limit.get())
                    self.idle_trainer.max_gpu = float(self.idle_gpu_limit.get())
                except: pass
                
            def _refresh_idle_status():
                if self.idle_trainer:
                    self.idle_trained_cnt.set(str(self.idle_trainer.trained_count))
                self.root.after(2000, _refresh_idle_status)
            
            _refresh_idle_status()
            
            # Row 1: Enable & Duration
            r1 = ttk.Frame(idle_frame)
            r1.pack(fill="x", pady=2)
            ttk.Checkbutton(r1, text="启用后台训练", variable=self.idle_enable_var, command=_toggle_idle).pack(side="left")
            ttk.Label(r1, text="持续时长(小时):").pack(side="left", padx=(15, 5))
            ttk.Entry(r1, textvariable=self.idle_duration_hours, width=5).pack(side="left")
            
            # Row 2: Resources
            r2 = ttk.Frame(idle_frame)
            r2.pack(fill="x", pady=2)
            ttk.Label(r2, text="如果 CPU 低于").pack(side="left")
            ttk.Entry(r2, textvariable=self.idle_cpu_limit, width=4).pack(side="left", padx=5)
            ttk.Label(r2, text="% 且内存低于").pack(side="left")
            ttk.Entry(r2, textvariable=self.idle_ram_limit, width=4).pack(side="left", padx=5)
            ttk.Label(r2, text="% 且 GPU 低于").pack(side="left")
            ttk.Entry(r2, textvariable=self.idle_gpu_limit, width=4).pack(side="left", padx=5)
            ttk.Label(r2, text="% 才启动").pack(side="left")
            ttk.Label(r2, text="已后台训练:").pack(side="left", padx=(20, 5))
            ttk.Label(r2, textvariable=self.idle_trained_cnt, foreground="blue").pack(side="left")
            
            self.idle_duration_hours.trace_add("write", _update_idle_cfg)
            self.idle_cpu_limit.trace_add("write", _update_idle_cfg)
            self.idle_ram_limit.trace_add("write", _update_idle_cfg)
            self.idle_gpu_limit.trace_add("write", _update_idle_cfg)

        # 操作按钮
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill="x", pady=(4, 6))
        self.auto_test_run_btn = ttk.Button(action_frame, text="开始", command=self._start_auto_test)
        self.auto_test_run_btn.pack(side="left")
        self.auto_test_stop_btn = ttk.Button(action_frame, text="停止", command=self._stop_auto_test, state="disabled")
        self.auto_test_stop_btn.pack(side="left", padx=6)
        self.auto_test_status_var = tk.StringVar(value="待机")
        ttk.Label(action_frame, textvariable=self.auto_test_status_var).pack(side="right")

        # 进度与日志
        self.auto_test_progress = ttk.Progressbar(main_frame, mode="determinate")
        self.auto_test_progress.pack(fill="x", pady=4)

        stats_frame = ttk.LabelFrame(main_frame, text="统计", padding=8)
        stats_frame.pack(fill="x", pady=6)
        ttk.Label(stats_frame, text="生成耗时:").grid(row=0, column=0, sticky="w")
        ttk.Label(stats_frame, textvariable=self.auto_test_gen_time_var).grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(stats_frame, text="训练耗时:").grid(row=0, column=2, sticky="w")
        ttk.Label(stats_frame, textvariable=self.auto_test_train_time_var).grid(row=0, column=3, sticky="w", padx=6)
        ttk.Label(stats_frame, text="总耗时:").grid(row=0, column=4, sticky="w")
        ttk.Label(stats_frame, textvariable=self.auto_test_total_time_var).grid(row=0, column=5, sticky="w", padx=6)

        ttk.Label(stats_frame, text="命中率:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Label(stats_frame, textvariable=self.auto_test_hit_rate_var).grid(row=1, column=1, sticky="w", padx=6, pady=4)
        ttk.Label(stats_frame, text="误报率:").grid(row=1, column=2, sticky="w", pady=4)
        ttk.Label(stats_frame, textvariable=self.auto_test_fp_rate_var).grid(row=1, column=3, sticky="w", padx=6, pady=4)
        ttk.Label(stats_frame, text="样本数:").grid(row=1, column=4, sticky="w", pady=4)
        ttk.Label(stats_frame, textvariable=self.auto_test_samples_var).grid(row=1, column=5, sticky="w", padx=6, pady=4)

        self.auto_test_log = scrolledtext.ScrolledText(main_frame, height=6, state="disabled")
        self.auto_test_log.pack(fill="both", expand=True)

    def _choose_auto_test_dir(self):
        try:
            p = filedialog.askdirectory(title="选择输出目录")
            if p:
                self.auto_test_output_var.set(p)
        except Exception:
            pass

    def _choose_auto_test_report(self):
        try:
            p = filedialog.asksaveasfilename(
                title="选择报告文件",
                defaultextension=".json",
                filetypes=[("JSON", "*.json"), ("CSV", "*.csv")],
            )
            if p:
                self.auto_test_report_var.set(p)
        except Exception:
            pass

    def _start_auto_test(self):
        if not HAS_LOG_GENERATOR:
            return
        if getattr(self, "_auto_test_running", False):
            return

        try:
            size_str = self.auto_test_size_var.get().strip()
            target_bytes = parse_size(size_str) if parse_size else 2 * 1024 * 1024
        except Exception:
            messagebox.showerror("参数错误", "日志大小格式无效，例如 2MB/512KB")
            return

        # Max single size input was removed from UI, defaulting to None (let target_bytes decide) or a safe high default
        max_single = None 

        try:
            count = int(self.auto_test_count_var.get())
            if count <= 0:
                raise ValueError
        except Exception:
            messagebox.showerror("参数错误", "数量必须为正整数")
            return

        seed = None
        seed_str = self.auto_test_seed_var.get().strip()
        if seed_str:
            try:
                seed = int(seed_str)
            except Exception:
                messagebox.showerror("参数错误", "随机种子必须为整数")
                return

        selected = self.auto_test_scenario_list.curselection()
        scenarios = []
        for idx in selected:
            raw = self.auto_test_scenario_list.get(idx)
            scenarios.append(raw.split("-")[0].strip())
        if not scenarios:
            scenarios = ["normal"]

        output_dir = self.auto_test_output_var.get().strip() or os.path.join(BASE_DIR, "analysis_data", "auto_tests")
        
        # Security validation for output path
        if not InputSanitizer.validate_dir_path(output_dir, create=True):
             self._auto_test_write_log(f"错误: 输出目录路径非法或父目录不可写: {output_dir}")
             return

        report_path = self.auto_test_report_var.get().strip() or None
        train = bool(self.auto_test_train_var.get())
        isolated = bool(self.auto_test_isolated_var.get())

        self._auto_test_cancel_event.clear()
        self._auto_test_running = True
        self.auto_test_run_btn.config(state="disabled")
        self.auto_test_stop_btn.config(state="normal")
        self.auto_test_progress.config(value=0, maximum=max(count, 1))
        self._auto_test_write_log("开始自动化测试...")
        self.auto_test_status_var.set("运行中")

        threading.Thread(
            target=self._auto_test_worker,
            args=(output_dir, target_bytes, seed, scenarios, count, report_path, train, isolated, max_single),
            daemon=True,
        ).start()

    def _stop_auto_test(self):
        try:
            self._auto_test_cancel_event.set()
            self.auto_test_status_var.set("正在停止")
        except Exception:
            pass

    def _auto_test_worker(self, output_dir, target_bytes, seed, scenarios, count, report_path, train, isolated, max_single):
        try:
            self._auto_test_write_log(f"生成日志：{count} 份，场景: {', '.join(scenarios)}")
            self.auto_test_status_var.set("生成中")
            t0 = time.time()

            def _progress_cb(stage, idx, total, file_path, scenario):
                if stage == "generate":
                    self._auto_test_write_log(f"[{idx}/{total}] 生成: {os.path.basename(file_path)} (场景 {scenario})")
                    self.root.after(0, lambda v=idx: self.auto_test_progress.config(value=v))

            summary = generate_batch(
                output_dir,
                target_bytes,
                seed,
                scenarios,
                count,
                report_path,
                progress_cb=_progress_cb,
                cancel_cb=lambda: self._auto_test_cancel_event.is_set(),
                max_single_size=max_single,
            )
            if summary is None:
                summary = []
            gen_time = time.time() - t0
            self.root.after(0, lambda: self.auto_test_gen_time_var.set(self._format_duration(gen_time)))

            self._auto_test_write_log(f"生成完成，共 {len(summary)} 份日志")

            if train:
                self.auto_test_status_var.set("训练中")
                self.auto_test_progress.config(value=0, maximum=max(len(summary), 1))
                t1 = time.time()
                train_time_acc = 0.0
                hit_count = 0
                fp_count = 0
                eval_count = 0
                if isolated:
                    synth_path = os.path.join(BASE_DIR, "analysis_data", "learned_patterns_synth.json")
                    try:
                        learner = CrashPatternLearner(synth_path)
                    except Exception:
                        learner = self.crash_pattern_learner
                else:
                    learner = self.crash_pattern_learner

                for idx, item in enumerate(summary):
                    if self._auto_test_cancel_event.is_set():
                        self._auto_test_write_log("已请求停止，训练中止")
                        break
                    file_path = item.get("file")
                    try:
                        log_text = read_text_head(file_path, max_bytes=LAB_HEAD_READ_SIZE)
                    except Exception:
                        self._auto_test_write_log(f"读取失败: {file_path}")
                        continue
                    self._auto_test_write_log(f"[{idx+1}/{len(summary)}] 训练: {os.path.basename(file_path)}")
                    s0 = time.perf_counter()
                    result = self._run_analysis_for_training(log_text, file_path, learner)
                    train_time_acc += (time.perf_counter() - s0)
                    scenario = item.get("scenario")
                    if scenario:
                        if result:
                            hit, fp = self._score_auto_test_result(scenario, result)
                            details = result.get("cause_counts", {}) if isinstance(result, dict) else {}
                            self._auto_test_write_log(f"[{idx+1}] 评分: hit={hit}, fp={fp}, causes={details}")
                        else:
                            self._auto_test_write_log(f"[{idx+1}] 训练分析为空，使用日志回退评分")
                            hit, fp = self._score_auto_test_fallback(scenario, log_text)
                            self._auto_test_write_log(f"[{idx+1}] 回退评分: hit={hit}, fp={fp}")
                        if hit:
                            hit_count += 1
                        if fp:
                            fp_count += 1
                    else:
                        self._auto_test_write_log(f"[{idx+1}] 缺少场景标签，跳过评分")
                    eval_count += 1
                    self.root.after(0, lambda v=idx+1: self.auto_test_progress.config(value=v))

                train_time = max(train_time_acc, time.time() - t1, 0.001)
                total_time = time.time() - t0
                self.root.after(0, lambda: self.auto_test_train_time_var.set(self._format_duration(train_time)))
                self.root.after(0, lambda: self.auto_test_total_time_var.set(self._format_duration(total_time)))
                hit_rate = hit_count / max(eval_count, 1)
                fp_rate = fp_count / max(eval_count, 1)
                self.root.after(0, lambda: self.auto_test_hit_rate_var.set(f"{hit_rate:.0%}"))
                self.root.after(0, lambda: self.auto_test_fp_rate_var.set(f"{fp_rate:.0%}"))
                self.root.after(0, lambda: self.auto_test_samples_var.set(str(eval_count)))
                self._auto_test_write_log(f"评分汇总: hit={hit_count}, fp={fp_count}, samples={eval_count}")
                self._auto_test_last_summary = {
                    "generated": len(summary),
                    "trained": len(summary),
                    "gen_time": gen_time,
                    "train_time": train_time,
                    "total_time": total_time,
                    "hit_rate": hit_count / max(eval_count, 1),
                    "fp_rate": fp_count / max(eval_count, 1),
                    "samples": eval_count,
                    "report": report_path,
                }
            else:
                total_time = time.time() - t0
                self.root.after(0, lambda: self.auto_test_total_time_var.set(self._format_duration(total_time)))
                self._auto_test_last_summary = {
                    "generated": len(summary),
                    "trained": 0,
                    "gen_time": gen_time,
                    "train_time": 0.0,
                    "total_time": total_time,
                    "hit_rate": 0.0,
                    "fp_rate": 0.0,
                    "samples": 0,
                    "report": report_path,
                }

            self._auto_test_write_log("自动化测试完成")
            if report_path:
                self._auto_test_write_log(f"报告已输出: {report_path}")
            
            # Update pattern count
            if self.crash_pattern_learner:
                cnt = self.crash_pattern_learner.get_pattern_count()
                self.root.after(0, lambda: self.auto_test_patterns_var.set(f"当前已习得模式数: {cnt}"))

            # --- Auto Cleanup ---
            if self.auto_test_cleanup_var.get() and summary:
                self._auto_test_write_log("正在清理生成的文件...")
                cnt = 0
                for item in summary:
                    try:
                        fp = item.get("file")
                        if fp and os.path.exists(fp):
                            os.remove(fp)
                            cnt += 1
                    except Exception:
                        pass
                self._auto_test_write_log(f"清理完成，删除了 {cnt} 个文件。")

        except Exception as e:
            self._auto_test_write_log(f"自动化测试失败: {e}")
        finally:
            self.root.after(0, self._auto_test_finish)

    def _auto_test_finish(self):
        self._auto_test_running = False
        try:
            self.auto_test_run_btn.config(state="normal")
            self.auto_test_stop_btn.config(state="disabled")
            self.auto_test_status_var.set("已完成")
        except Exception:
            pass
        try:
            if self._auto_test_last_summary:
                self._show_auto_test_summary(self._auto_test_last_summary)
        except Exception:
            pass

    def _auto_test_write_log(self, msg: str):
        def _write():
            try:
                self.auto_test_log.config(state="normal")
                self.auto_test_log.insert(tk.END, msg + "\n")
                self.auto_test_log.see(tk.END)
                self.auto_test_log.config(state="disabled")
                
                # 同时打印到控制台，确保即使 UI 反应慢也能看到
                print(f"[AutoTest] {msg}")
            except Exception:
                pass
        self.root.after(0, _write)

    def _format_duration(self, seconds: float) -> str:
        try:
            if seconds < 1:
                ms = max(int(seconds * 1000), 1)
                return f"{ms}ms"
            return f"{seconds:.2f}s"
        except Exception:
            return "-"

    def _show_auto_test_summary(self, summary: dict):
        msg = (
            f"自动化测试完成\n"
            f"生成日志: {summary.get('generated', 0)}\n"
            f"训练样本: {summary.get('samples', 0)}\n"
            f"命中率: {summary.get('hit_rate', 0.0):.0%}\n"
            f"误报率: {summary.get('fp_rate', 0.0):.0%}\n"
            f"生成耗时: {summary.get('gen_time', 0.0):.2f}s\n"
            f"训练耗时: {summary.get('train_time', 0.0):.2f}s\n"
            f"总耗时: {summary.get('total_time', 0.0):.2f}s\n"
        )
        report = summary.get("report")
        if report:
            msg += f"报告: {report}\n"

        self._auto_test_write_log("===== 自动化测试总结 =====")
        self._auto_test_write_log(msg.strip())
        self._auto_test_write_log("========================")
        try:
            messagebox.showinfo("自动化测试完成", msg)
        except Exception:
            pass

    def _run_analysis_for_training(self, log_text: str, file_path: str, learner: CrashPatternLearner | None):
        # 标记正在进行自动化测试，抑制 UI 更新
        self._is_auto_testing = True
        
        # 备份当前 UI 状态，避免影响用户界面
        backup = {
            "crash_log": self.crash_log,
            "file_path": self.file_path,
            "analysis_results": list(self.analysis_results),
            "mods": defaultdict(set, self.mods),
            "mod_names": dict(self.mod_names),
            "dependency_pairs": set(self.dependency_pairs),
            "loader_type": self.loader_type,
            "cause_counts": Counter(self.cause_counts),
            "file_checksum": self.file_checksum,
            "log_cache_raw": getattr(self, "_log_cache_raw", None),
            "log_cache_lower": getattr(self, "_log_cache_lower", None),
            "log_cache_lines": getattr(self, "_log_cache_lines", None),
            "log_cache_lower_lines": getattr(self, "_log_cache_lower_lines", None),
        }
        old_learner = self.crash_pattern_learner
        old_cancel = getattr(self, "_cancel_event", None)

        try:
            self.crash_log = log_text or ""
            self.file_path = file_path or ""
            self.file_checksum = None
            self.analysis_results = []
            self.mods = defaultdict(set)
            self.mod_names = {}
            self.dependency_pairs = set()
            self.loader_type = None
            self.cause_counts = Counter()
            self._invalidate_log_cache()
            # 临时重置图表缓存 Key，防止测试数据污染图表状态
            self._graph_cache_key = None 

            # 训练期间禁用全局取消标记，避免误触导致直接退出
            self._cancel_event = threading.Event()
            self._cancel_event.clear()

            if learner is not None:
                self.crash_pattern_learner = learner

            self._run_analysis_logic()
            return {
                "analysis_results": list(self.analysis_results),
                "loader": self.loader_type,
                "cause_counts": dict(self.cause_counts),
            }
        except Exception as e:
            self._auto_test_write_log(f"训练分析失败: {type(e).__name__}: {e}")
        finally:
            self._is_auto_testing = False  # 恢复标记
            self.crash_pattern_learner = old_learner
            self._cancel_event = old_cancel
            self.crash_log = backup["crash_log"]
            self.file_path = backup["file_path"]
            self.analysis_results = backup["analysis_results"]
            self.mods = backup["mods"]
            self.mod_names = backup["mod_names"]
            self.dependency_pairs = backup["dependency_pairs"]
            self.loader_type = backup["loader_type"]
            self.cause_counts = backup["cause_counts"]
            self.file_checksum = backup["file_checksum"]
            self._log_cache_raw = backup["log_cache_raw"]
            self._log_cache_lower = backup["log_cache_lower"]
            self._log_cache_lines = backup["log_cache_lines"]
            self._log_cache_lower_lines = backup["log_cache_lower_lines"]

    def _score_auto_test_result(self, scenario: str, result: dict) -> tuple[bool, bool]:
        """返回 (hit, false_positive)。

        hit: 非 normal 场景命中预期关键词。
        false_positive: normal 场景被错误识别为异常。
        """
        texts = "\n".join(result.get("analysis_results", [])).lower()
        causes = result.get("cause_counts", {}) or {}

        indicators = {
            "oom": ["outofmemory", "内存", "heap"],
            "missing_dependency": ["missing mod", "missing or unsupported", "依赖", "requires", "缺失"],
            "gl_error": ["opengl", "glfw", "gl ", "渲染"],
            "mixin_conflict": ["mixin", "混入", "conflict", "incompatible"],
            "version_conflict": ["版本", "version", "incompatible"],
            "compound": ["outofmemory", "missing mod", "mixin", "opengl", "版本", "依赖"],
        }

        cause_expect = {
            "oom": CAUSE_MEM,
            "missing_dependency": CAUSE_DEP,
            "version_conflict": CAUSE_VER,
            "gl_error": CAUSE_GPU,
            "compound": CAUSE_OTHER,
            "mixin_conflict": CAUSE_OTHER,
        }

        if scenario == "normal":
            error_keywords = [
                "outofmemory", "missing mod", "mixin", "opengl", "glfw", "版本", "依赖", "错误", "崩溃"
            ]
            false_positive = any(k in texts for k in error_keywords)
            if any(v > 0 for v in causes.values()):
                false_positive = True
            return False, false_positive

        keys = indicators.get(scenario, [])
        hit = any(k in texts for k in keys)
        expected_cause = cause_expect.get(scenario)
        if expected_cause and causes.get(expected_cause, 0) > 0:
            hit = True
        return hit, False

    def _score_auto_test_fallback(self, scenario: str, log_text: str) -> tuple[bool, bool]:
        lower = (log_text or "").lower()
        indicators = {
            "oom": ["outofmemoryerror", "out of memory", "heap space"],
            "missing_dependency": ["missing or unsupported mandatory dependencies", "mod id:", "requires"],
            "gl_error": ["glfw error", "opengl error", "gl_invalid"],
            "mixin_conflict": ["mixin apply failed", "invalid mixin"],
            "version_conflict": ["found mod file /mods/", "incompatible with loaded version"],
            "compound": ["missing or unsupported", "outofmemoryerror", "opengl error", "mixin apply failed"],
        }
        if scenario == "normal":
            error_keywords = ["outofmemory", "missing or unsupported", "mixin", "opengl", "glfw", "incompatible"]
            return False, any(k in lower for k in error_keywords)
        return any(k in lower for k in indicators.get(scenario, [])), False

    def _detect_gl_errors(self):
        """Invoke GL detector standalone for hardware tab refresh."""
        if hasattr(self, '_gl_errors_detector') and self._gl_errors_detector:
            ctx = AnalysisContext(self, self.crash_log or "")
            self._gl_errors_detector.detect(self.crash_log or "", ctx)

    def _refresh_hardware_analysis(self):
        # 重新运行 GL 检测并展示在硬件页
        try:
            self._detect_gl_errors()
        except Exception:
            pass
        # 更新 hw_text
        try:
            self.hw_text.config(state="normal")
            self.hw_text.delete("1.0", tk.END)
            if self.gpu_info:
                for k, v in self.gpu_info.items():
                    self.hw_text.insert(tk.END, f"{k}: {v}\n")
            if self.hardware_issues:
                self.hw_text.insert(tk.END, "\n硬件相关建议:\n")
                for l in self.hardware_issues:
                    self.hw_text.insert(tk.END, "- " + l + "\n")
            # 加入 GL snippets
            if getattr(self, 'gl_snippets', None):
                self.hw_text.insert(tk.END, "\nGL/Shader 相关片段:\n")
                for s in self.gl_snippets:
                    self.hw_text.insert(tk.END, s + "\n---\n")
            self.hw_text.config(state="disabled")
        except Exception:
            pass

    def _copy_gl_snippets(self):
        try:
            txt = "\n---\n".join(self.gl_snippets or [])
            self.root.clipboard_clear()
            self.root.clipboard_append(txt)
            messagebox.showinfo("复制成功", "GL 相关片段已复制到剪贴板，方便粘贴到问题帖或日志分享。")
        except Exception:
            messagebox.showerror("复制失败", "无法复制到剪贴板。")

    def browser_back(self):
        try:
            if hasattr(self, "browser") and self.browser:
                # tkinterweb 的接口可能不同，兼容处理
                try:
                    self.browser.go_back()
                except Exception:
                    try:
                        self.browser.back()
                    except Exception:
                        pass
        except Exception:
            pass

    def browser_forward(self):
        try:
            if hasattr(self, "browser") and self.browser:
                try:
                    self.browser.go_forward()
                except Exception:
                    try:
                        self.browser.forward()
                    except Exception:
                        pass
        except Exception:
            pass

    def browser_reload(self):
        try:
            if hasattr(self, "browser") and self.browser:
                try:
                    self.browser.reload()
                except Exception:
                    try:
                        self.browser.refresh()
                    except Exception:
                        pass
        except Exception:
            pass

    def setup_solution_browser(self, init_only: bool = False):
        """
        在 web_tab 中创建在线解决方案面板：
        - 若安装了 tkinterweb (HtmlFrame)，则嵌入浏览器（兼容多种加载方法）;
        - 否则显示占位提示并提供在外部浏览器打开的按钮。
        init_only=True 时仅创建控件/占位（用于初始化 UI），不强制加载远程页面。
        """
        # 清理旧内容
        try:
            for w in getattr(self, "web_tab", ttk.Frame()).winfo_children():
                w.destroy()
        except Exception:
            pass

        # 控件行: 搜索框 + 按钮
        ctrl = ttk.Frame(self.web_tab, padding=6)
        ctrl.pack(fill="x", padx=6, pady=(6, 0))
        self.web_search_var = tk.StringVar(value="minecraft crash solutions")
        ttk.Entry(ctrl, textvariable=self.web_search_var).pack(side="left", fill="x", expand=True, padx=(0,6))
        def _do_search():
            query = self.web_search_var.get().strip()
            if not query:
                return
            url = f"https://www.bing.com/search?q={query.replace(' ', '+')}"
            # 若可嵌入，则尝试在 HtmlFrame 中加载。
            if HAS_HTMLFRAME and hasattr(self, 'browser') and self.browser:
                try:
                    # 有些版本 API 为 load_website/load_url/set_content
                    try:
                        self.browser.load_website(url)
                        return
                    except Exception:
                        pass
                    try:
                        self.browser.load_url(url)
                        return
                    except Exception:
                        pass
                    try:
                        self.browser.set_content(f'<iframe src="{url}" style="border:0;width:100%;height:100%"></iframe>')
                        return
                    except Exception:
                        pass
                except Exception:
                    logger.exception("在 HtmlFrame 中加载 URL 失败，回退到外部浏览器")
            # fallback: 在外部浏览器打开
            safe_url = InputSanitizer.sanitize_url(url)
            if safe_url:
                webbrowser.open(safe_url)

        ttk.Button(ctrl, text="搜索", command=_do_search, width=10).pack(side="left", padx=2)
        
        def _open_external_search():
            q = self.web_search_var.get().strip().replace(' ','+')
            url = f"https://www.bing.com/search?q={q}"
            safe = InputSanitizer.sanitize_url(url)
            if safe:
                webbrowser.open(safe)

        ttk.Button(ctrl, text="在外部浏览器打开", command=_open_external_search, width=18).pack(side="right", padx=2)

        # 有用链接和说明区域
        links_frame = ttk.Frame(self.web_tab, padding=6)
        links_frame.pack(fill="x", padx=6, pady=(4,0))
        ttk.Label(links_frame, text="常用搜索/资源:").pack(side="left")
        def _open_link(q):
            try:
                raw_url = f"https://www.bing.com/search?q={q.replace(' ','+')}"
                safe = InputSanitizer.sanitize_url(raw_url)
                if safe:
                    webbrowser.open(safe)
            except Exception:
                pass
        for txt, q in [("Crash 系统日志 模式","minecraft crash log common causes"), ("GeckoLib 错误","geckolib missing mod crash"), ("OpenGL / GLFW 错误","opengl glfw crash minecraft")]:
            ttk.Button(links_frame, text=txt, command=lambda qq=q: _open_link(qq), width=18).pack(side="left", padx=4)

        # 如果没有 HtmlFrame，显示提示文本并返回（用户可点外部浏览器或搜索）
        if not HAS_HTMLFRAME:
            st = scrolledtext.ScrolledText(self.web_tab, height=12)
            st.pack(fill="both", expand=True, padx=6, pady=(6,8))
            st.insert(tk.END, "未检测到 tkinterweb，无法嵌入网页。")
            st.insert(tk.END, "\n请使用上方搜索或点击“在外部浏览器打开”。\n\n常用资源:\n")
            st.insert(tk.END, "- https://www.bing.com/search?q=minecraft+crash+solutions\n")
            st.insert(tk.END, "- https://www.reddit.com/r/MinecraftHelp/\n")
            st.insert(tk.END, "- https://github.com/search?q=minecraft+crash\n")
            st.config(state="disabled")
            self.browser = None
            return

        # 尝试创建 HtmlFrame 并展示初始内容或占位
        try:
            # create or reuse browser
            try:
                self.browser = HtmlFrame(self.web_tab, messages_enabled=False)
            except Exception:
                # some versions require different init args
                try:
                    self.browser = HtmlFrame(self.web_tab)
                except Exception as e:
                    self.browser = None
                    logger.exception("HtmlFrame 初始化失败: %s", e)
            if not self.browser:
                ttk.Label(self.web_tab, text="嵌入浏览器不可用（HtmlFrame init failed）", foreground="#c00").pack(expand=True)
                return

            if not init_only:
                # 加载默认搜索结果页面
                try:
                    self.browser.load_website("https://www.bing.com/search?q=minecraft+crash+solutions")
                except Exception:
                    try:
                        self.browser.load_url("https://www.bing.com/search?q=minecraft+crash+solutions")
                    except Exception:
                        try:
                            self.browser.set_content("<h3>在线解决方案：请使用右上方搜索或在外部浏览器打开。</h3>")
                        except Exception:
                            pass
            else:
                try:
                    self.browser.set_content("<h3>在线解决方案：输入查询并点击 搜索 或 使用外部浏览器。</h3>")
                except Exception:
                    pass

            self.browser.pack(fill="both", expand=True, padx=6, pady=(6,8))
        except Exception as e:
            ttk.Label(self.web_tab, text=f"嵌入浏览器初始化失败: {e}", foreground="#c00").pack(expand=True)
            self.browser = None

    # ---------- file / log handling ----------
    def load_file(self):
        # Support selecting multiple files
        paths = filedialog.askopenfilenames(filetypes=[("日志文件", "*.log *.txt"), ("所有文件", "*.*")])
        if not paths:
            return
        
        if len(paths) == 1:
            self.detect_and_load_file(paths[0])
        else:
            self.detect_and_load_multiple_files(paths)

    def detect_and_load_multiple_files(self, paths):
        try:
            combined_log = []
            total_size = 0
            
            # Sort paths to keep order consistent (e.g. by name)
            sorted_paths = sorted(list(paths))
            
            for fpath in sorted_paths:
                if not InputSanitizer.validate_file_path(fpath):
                    continue
                
                fname = os.path.basename(fpath)
                header = f"\n{'='*60}\n>>> JOINT ANALYSIS - FILE: {fname} <<<\n{'='*60}\n"
                
                try:
                    fsize = os.path.getsize(fpath)
                except:
                    fsize = 0
                
                # Check total size limit (e.g. 50MB combined limit)
                if total_size + fsize > DEFAULT_MAX_BYTES * 5:
                    combined_log.append(header + f"\n[Skipped {fname}: Total size limit exceeded]")
                    continue

                content = read_text_limited(fpath, max_bytes=DEFAULT_MAX_BYTES)
                combined_log.append(header)
                combined_log.append(content)
                total_size += len(content)
                
            full_data = "".join(combined_log)
            
            # Update State
            self.file_path = " + ".join([os.path.basename(p) for p in sorted_paths[:3]])
            if len(sorted_paths) > 3: 
                self.file_path += f" ... (+{len(sorted_paths)-3} more)"
                
            self.crash_log = full_data
            
             # Compute checksum for caching (on combined data)
            try:
                self.file_checksum = hashlib.sha256(full_data.encode('utf-8', 'ignore')).hexdigest()
            except Exception:
                self.file_checksum = None

            self._invalidate_log_cache()
            self.update_log_text()
            self.status_var.set(f"已加载 {len(sorted_paths)} 个文件用于联合分析")

        except Exception as e:
            messagebox.showerror("批量加载失败", f"错误: {e}")
            self.status_var.set("加载失败")

    def detect_and_load_file(self, file_path):
        try:
            if not InputSanitizer.validate_file_path(file_path):
                raise ValueError("无效的文件路径")
            # stream-read with safety cap to avoid huge memory spike
            try:
                file_size = os.path.getsize(file_path)
            except Exception:
                file_size = 0
            if file_size > DEFAULT_MAX_BYTES:
                chunks = []
                read_total = 0
                max_bytes = DEFAULT_MAX_BYTES

                def _on_chunk(chunk):
                    nonlocal read_total
                    if read_total >= max_bytes:
                        return False
                    take = min(len(chunk.content), max_bytes - read_total)
                    if take > 0:
                        chunks.append(chunk.content[:take])
                        read_total += take
                        try:
                            self.progress_reporter.report(read_total / max_bytes, "加载日志中...")
                        except Exception:
                            pass
                    if read_total >= max_bytes:
                        return False

                StreamingLogAnalyzer(file_path, chunk_size=256 * 1024).analyze_incremental(_on_chunk)
                data = "".join(chunks)
            else:
                data = read_text_limited(file_path)
            self.file_path = file_path
            self.crash_log = data
            
            # Compute checksum for caching
            try:
                self.file_checksum = hashlib.sha256(data.encode('utf-8', 'ignore')).hexdigest()
            except Exception:
                self.file_checksum = None

            self._invalidate_log_cache()
            self.update_log_text()
            self.status_var.set(f"已加载: {os.path.basename(file_path)}")
        except Exception as e:
            messagebox.showerror("加载失败", f"无法读取文件: {e}")
            self.status_var.set("加载失败")

    def update_log_text(self):
        try:
            yview = self.log_text.yview()
        except Exception:
            yview = None

        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.insert(tk.END, self.crash_log)

        if len(self.crash_log) <= getattr(self, "highlight_size_limit", HIGHLIGHT_SIZE_LIMIT):
            keywords = ["exception", "error", "crash", "outofmemory", "out of memory", "FAILED", "FATAL"]
            for kw in keywords:
                start_idx = "1.0"
                while True:
                    start_idx = self.log_text.search(kw, start_idx, stopindex=tk.END, nocase=True)
                    if not start_idx:
                        break
                    end_idx = f"{start_idx}+{len(kw)}c"
                    try:
                        self.log_text.tag_add("highlight", start_idx, end_idx)
                    except Exception:
                        pass
                    start_idx = end_idx

        try:
            if yview:
                self.log_text.yview_moveto(yview[0])
        except Exception:
            pass
        finally:
            self.log_text.config(state="disabled")

    def clear_content(self):
        self.crash_log = ""
        self.file_path = ""
        self.analysis_results = []
        self._invalidate_log_cache()
        self.mods = defaultdict(set)
        self.mod_names = {}
        self.dependency_pairs = set()
        self.loader_type = None
        self.cause_counts = Counter()
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state="disabled") # Restore read-only state
        self.result_text.config(state="normal")
        self.result_text.delete("1.0", tk.END)
        self.result_text.config(state="disabled")
        self.status_var.set("已清除")
        for w in self.canvas_container.winfo_children():
            w.destroy()
        self.graph_placeholder = ttk.Label(self.canvas_container, text="分析后显示依赖关系图", foreground="#666666")
        self.graph_placeholder.pack(expand=True)
        self.gpu_info = {}
        self.hardware_issues = []
        self.gl_snippets = []
        try:
            self.hw_text.config(state="normal")
            self.hw_text.delete("1.0", tk.END)
            self.hw_text.config(state="disabled")
        except Exception:
            pass
        for w in self.cause_canvas_container.winfo_children():
            w.destroy()
        self.cause_placeholder = ttk.Label(self.cause_canvas_container, text="分析后显示崩溃原因占比", foreground="#666666")
        self.cause_placeholder.pack(expand=True)


    def _is_cancelled(self):
        # 兼容旧代码，如果没有 _cancel_event 属性则不取消
        evt = getattr(self, "_cancel_event", None)
        return evt.is_set() if evt else False

    def start_analysis(self):
        self._reload_config_if_changed()
        if not self.crash_log:
            messagebox.showinfo("提示", "请先加载崩溃日志文件。")
            return
        
        # 防止在自动化测试运行时手动启动分析，避免状态冲突
        if getattr(self, "_is_auto_testing", False):
            messagebox.showwarning("忙碌", "自动化测试正在运行中，请等待其完成或停止后再试。")
            return

        # 初始化并发控制
        if not hasattr(self, '_cancel_event'):
            self._cancel_event = threading.Event()
        self._cancel_event.clear()

        # UI 反馈
        self.progress.pack(fill="x", padx=10, pady=(4, 6))
        self.progress.config(mode="indeterminate")
        self.progress.start(10)
        self.status_var.set("正在分析...")

        # 启动后台任务
        # 使用 TaskExecutor 统一管理，若不可用则回退到 Thread
        if hasattr(self, 'task_executor') and self.task_executor:
            self.task_executor.submit_analysis_task(self._run_analysis_thread, lambda r: None)
        else:
            threading.Thread(target=self._run_analysis_thread, daemon=True).start()

    def _report_progress(self, val: float, msg: str = ""):
        # 自动化测试模式下，抑制主界面进度条更新，避免闪烁和性能损耗
        if getattr(self, "_is_auto_testing", False):
            return

        self.root.after(0, lambda: self.status_var.set(msg))
        if hasattr(self, 'progress_reporter'):
            self.progress_reporter.report(val, msg)

    def _run_analysis_logic(self):
        """主分析流程逻辑，替代原 AnalysisEngine。"""
        # 0) 预备检查
        if self._is_cancelled(): raise TaskCancelledError

        # 1) 检测加载器
        self.loader_type = self._detect_loader()
        self._report_progress(1/6, "检测加载器")

        # 2) 提取 Mod (使用优化后的正则)
        if self._is_cancelled(): raise TaskCancelledError
        self._extract_mods()
        self._report_progress(2/6, "提取 Mod 信息")

        # 3) 并行运行检测器
        if self._is_cancelled(): raise TaskCancelledError
        self._run_detectors()
        self._report_progress(3/6, "执行检测器")

        # 4) 智能诊断与依赖分析
        if self._is_cancelled(): raise TaskCancelledError
        if self.HAS_NEW_MODULES:
             self._run_smart_diagnostics()
             self._run_dependency_analysis()
        
        # 4.5) 智能学习模式 (配置启用时)
        if getattr(self, "app_config", None) and getattr(self.app_config, "enable_smart_learning", False):
            self._run_learning_based_analysis()

        self._report_progress(4/6, "智能诊断")

        # 5) 生成摘要
        self._build_precise_summary()
        self._report_progress(5/6, "生成摘要")

        # 6) 数据规整与去重
        self.analysis_results = list(dict.fromkeys(self.analysis_results))
        self._clean_dependency_pairs()
        
        # 7) 自动学习 (Auto-Learning)
        # 无论是否启用"智能建议"，我们都可以在后台积累知识库
        if self.crash_pattern_learner:
            try:
                self.crash_pattern_learner.learn_from_crash(self.crash_log, self.analysis_results)
            except Exception as e:
                logger.warning(f"智能学习记录失败: {e}")
        
        # 8) 插件回调
        for plugin in self.plugin_registry.list():
            try: plugin(self)
            except Exception as e: logger.warning(f"插件 {plugin} 执行异常: {e}")

    def add_cause(self, cause_label: str):
        """Thread-safe cause counting."""
        with self.lock:
            self.cause_counts[cause_label] += 1

    def _extract_mods(self):
        """使用优化后的 RegexCache 提取 Mod 信息。"""
        self.mods = defaultdict(set)
        text = self.crash_log or ""
        
        # 优化策略：
        # 1. 直接搜索 .jar 模式，跳过不包含 .jar 的无效行
        # 2. 模式解释:
        #    (?:^|\s)           行首或空白
        #    ([a-zA-Z0-9_\-]+)  Group 1: Mod ID (文件名主体)
        #    -
        #    (\d[\w\.\-]+)      Group 2: 版本号 (数字开头)
        #    \.jar              后缀
        pattern = r"(?:^|[\/\\])([a-zA-Z0-9_\-]+)-(\d[\w\.\-]+)\.jar"
        
        seen = set()
        # 复用 RegexCache，不必每次都 compile
        for m in RegexCache.finditer(pattern, text):
            raw_id, ver = m.groups()
            modid = self._clean_modid(raw_id)
            if modid and modid not in seen:
                self.mods[modid].add(ver)
                # 简单防重
                seen.add(f"{modid}:{ver}")
                
        self.analysis_results.append(f"扫描完成：发现 {len(self.mods)} 个模组文件。")




    def _run_detectors(self):
        self._extract_dependency_pairs()
        
        executor = None
        if self.brain:
            # 优先使用 Brain System 的托管线程池 (配置更优，带监控)
            executor = self.brain.thread_pool
            logger.info("使用 Brain System 算力加速检测器执行")
        
        # 根据核心数动态调整并行度
        workers = os.cpu_count() or 4
        # 限制最大线程，避免上下文切换开销过大
        workers = min(workers, 8) 
        
        detectors_list = self.detector_registry.list()
        if hasattr(self, "_auto_test_write_log"):
             self._auto_test_write_log(f"执行检测器: count={len(detectors_list)}, workers={workers}")
        
        self.detector_registry.run_all_parallel(self, max_workers=workers, executor=executor)

    def _run_analysis_thread(self):
        try:
            # 状态重置
            self.analysis_results.clear()
            self.cause_counts.clear()
            self._graph_cache_key = None
            self._graph_rendered = False
            
            # 缓存检查
            if self.file_checksum and self.file_checksum in self._analysis_cache:
                cached = self._analysis_cache[self.file_checksum]
                self.analysis_results[:] = cached['results']
                self.mods = cached['mods'] # 深拷贝已在缓存存入时做过，这里引用即可
                self.dependency_pairs = cached['dep_pairs']
                self.loader_type = cached['loader']
                
                self.cause_counts.clear()
                self.cause_counts.update(cached['causes'])
                
                self._report_progress(1.0, "分析完成 (缓存命中)")
                self._post_analysis_ui_update(cached=True)
                return

            # 执行核心逻辑
            self._run_analysis_logic()

            # 写入缓存
            if self.file_checksum:
                import copy
                self._analysis_cache[self.file_checksum] = {
                    'results': list(self.analysis_results),
                    'mods': copy.deepcopy(self.mods),
                    'dep_pairs': set(self.dependency_pairs),
                    'loader': self.loader_type,
                    'causes': self.cause_counts.copy()
                }

            # 记录历史并更新UI
            self._record_history()
            self._report_progress(1.0, "分析完成")
            self._post_analysis_ui_update(cached=False)

        except TaskCancelledError:
            self.analysis_results.append(">> 分析操作已由用户取消。")
            self._report_progress(0, "已取消")
            self.root.after(0, self.display_results)

        except Exception:
            logger.exception("分析过程发生不可预期的错误")
            self.analysis_results.append(f"分析出错: {sys.exc_info()[1]}")
            self._report_progress(0, "分析出错")
            self.root.after(0, self.display_results)
        
        finally:
            self.root.after(0, self.progress.stop)
            self.root.after(0, lambda: self.progress.pack_forget())

    def _post_analysis_ui_update(self, cached: bool):
        self.root.after(0, self.display_results)
        # 延迟渲染较重的图表
        delay = 100 if cached else 300
        self.root.after(delay, self.update_dependency_graph)
        self.root.after(delay, self.update_cause_chart)

    def _detect_loader(self):
        """检测加载器类型"""
        txt = (self.crash_log or "").lower()
        if "neoforge" in txt:
            return "NeoForge"
        if "forge" in txt and "fml" in txt:
            return "Forge"
        if "fabric loader" in txt or ("fabric" in txt and "quilt" not in txt):
            return "Fabric"
        if "quilt" in txt:
            return "Quilt"
        return "Unknown"

    def _clean_dependency_pairs(self):
        """简单的依赖对清理"""
        if not self.dependency_pairs: return
        self.dependency_pairs = {
            (p, c) for p, c in self.dependency_pairs 
            if p and c and p != c
        }



    def _extract_dependency_pairs(self):
        """Extraction using optimized RegexCache."""
        text = self.crash_log or ""
        # 常见依赖缺失模式
        # "Missing mod 'X' needed by 'Y'"
        p1 = r"Missing mod '([^']+)' needed by '([^']+)'"
        for m in RegexCache.finditer(p1, text):
            self.dependency_pairs.add((m.group(2), m.group(1)))
            self.analysis_results.append(f"发现依赖关系: {m.group(2)} -> {m.group(1)} (缺失)")

        # "Mod X requires Y"
        p2 = r"Mod ([^ ]+) requires ([^ \n]+)"
        for m in RegexCache.finditer(p2, text):
            self.dependency_pairs.add((m.group(1), m.group(2)))
        

    def _run_smart_diagnostics(self):
        # 简化调用，不再防御性检查每一层
        if self.diagnostic_engine and self.HAS_NEW_MODULES:
            res = self.diagnostic_engine.analyze(self.crash_log)
            if res:
               self.analysis_results.append(">> 智能诊断建议:")
               self.analysis_results.extend([f" - {r}" for r in res])

    def _run_learning_based_analysis(self):
        """执行基于历史模式的学习型分析"""
        if not self.crash_pattern_learner:
            return
        # 需要时才启动 AI 引擎，避免启动阶段卡死
        self._start_ai_init_if_needed()
            
        try:
            suggestions = self.crash_pattern_learner.suggest_solutions(self.crash_log)
            if suggestions:
                self.analysis_results.append(">> 智能学习引擎建议:")
                for s in suggestions:
                    self.analysis_results.append(f" - {s.text}")
        except Exception as e:
            logger.warning(f"智能学习分析执行出错: {e}")

    def _run_dependency_analysis(self):
         # 占位符：未来扩展依赖分析
         pass

    def _build_precise_summary(self):
        summary = [
            f"加载器: {self.loader_type.upper() if self.loader_type else '未知'}",
            f"Mod总数: {len(self.mods)}"
        ]
        # 将摘要插入头部
        self.analysis_results[0:0] = summary

    def _record_history(self):
        try:
            summary = "; ".join(self.analysis_results[:6])[:800]
            
            # 轮转和压缩策略
            try:
                if os.path.exists(HISTORY_FILE) and os.path.getsize(HISTORY_FILE) > 5 * 1024 * 1024: # 5MB 限制
                    import zipfile
                    import time
                    archive_path = os.path.join(os.path.dirname(HISTORY_FILE), "history_archive.zip")
                    with zipfile.ZipFile(archive_path, "a", zipfile.ZIP_DEFLATED) as zf:
                        zf.write(HISTORY_FILE, arclename=f"history_{int(time.time())}.csv")
                    # Clear original file (keeping utf-8-sig bom if needed, usually just empty is fine for append)
                    with open(HISTORY_FILE, "w", encoding="utf-8-sig", newline="") as f:
                        pass
            except Exception:
                pass


            with open(HISTORY_FILE, "a", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([datetime.now().isoformat(), summary, self.file_path])
        except Exception:
            pass

    def display_results(self):
        self.result_text.config(state="normal")
        self.result_text.delete("1.0", tk.END)
        
        if not self.analysis_results:
            self.result_text.config(state="disabled")
            return

        for line in self.analysis_results:
            if "智能" in line and "建议" in line:
                self.result_text.insert(tk.END, line + "\n", "ai_header")
            elif "AI 深度理解" in line or "关键特征匹配" in line:
                self.result_text.insert(tk.END, line + "\n", "ai_content")
            else:
                self.result_text.insert(tk.END, line + "\n")
                
        self.result_text.config(state="disabled")

    def update_dependency_graph(self, clear_only=False):
        if not HAS_NETWORKX:
            for w in self.canvas_container.winfo_children():
                w.destroy()
            ttk.Label(self.canvas_container, text="缺少依赖: networkx/matplotlib，无法绘制图表").pack(expand=True)
            return

        # Cleanup existing
        for w in self.canvas_container.winfo_children():
            w.destroy()
            
        if clear_only or (not self.mods and not self.dependency_pairs):
            ttk.Label(self.canvas_container, text="无依赖数据").pack(expand=True)
            return

        # Check render flag (lazy loading)
        if not self._graph_cache_key:
            self._graph_cache_key = (len(self.mods), len(self.dependency_pairs))
        
        # UI Feedback
        ttk.Label(self.canvas_container, text="正在计算布局 (后台线程)...").pack(expand=True)
        
        # Prepare parameters for thread
        layout_name = self.layout_var.get().split()[0].lower() if hasattr(self, 'layout_var') else 'spring'
        filter_iso = self.filter_isolated_var.get() if hasattr(self, 'filter_isolated_var') else True
        if self.mods and not self.dependency_pairs:
            filter_iso = False

        # Copy data to avoid thread modification issues
        import copy
        mods_keys = list(self.mods.keys())
        dep_pairs = copy.copy(self.dependency_pairs)

        threading.Thread(
            target=self._async_layout_worker,
            args=(mods_keys, dep_pairs, layout_name, filter_iso),
            daemon=True
        ).start()

    def _async_layout_worker(self, mods_keys, dep_pairs, layout_name, filter_iso):
        """Background thread for heavy graph layout calculation."""
        try:
            G = nx.DiGraph()
            
            # Construct graph
            for m in mods_keys:
                G.add_node(m)
            for a, b in dep_pairs:
                if a in mods_keys or b in mods_keys:
                     G.add_edge(a, b)

            # Filter
            if filter_iso:
                isolates = list(nx.isolates(G))
                G.remove_nodes_from(isolates)

            node_count = G.number_of_nodes()
            if node_count == 0:
                self.root.after(0, lambda: self._draw_computed_graph(None, None, "无关联节点 (已过滤孤立项)"))
                return
            
            # Limit nodes
            if node_count > GRAPH_NODE_LIMIT: 
                 degrees = sorted(G.degree, key=lambda x: x[1], reverse=True)
                 top_nodes = [n for n, d in degrees[:GRAPH_NODE_LIMIT]]
                 G = G.subgraph(top_nodes)
                 node_count = GRAPH_NODE_LIMIT # Approximate update

            # Layout Calculation (The Heavy Part)
            k_val = 1.0 / (node_count ** 0.5) if node_count > 0 else 0.5

            if layout_name == 'circular': pos = nx.circular_layout(G)
            elif layout_name == 'shell': pos = nx.shell_layout(G)
            elif layout_name == 'spectral': pos = nx.spectral_layout(G)
            elif layout_name == 'random': pos = nx.random_layout(G)
            else: pos = nx.spring_layout(G, k=k_val + 0.1, seed=42)

            self.root.after(0, lambda: self._draw_computed_graph(G, pos))
        except Exception as e:
            self.root.after(0, lambda: self._draw_computed_graph(None, None, str(e)))

    def _draw_computed_graph(self, G, pos, error_msg=None):
        """Main thread callback to render the pre-calculated graph."""
        # Clean loading label
        for w in self.canvas_container.winfo_children():
            w.destroy()

        if error_msg:
            ttk.Label(self.canvas_container, text=error_msg).pack(expand=True)
            return

        if not G or not pos:
             return

        try:
            from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
            
            fig = plt.Figure(figsize=(6, 5), dpi=100)
            ax = fig.add_subplot(111)

            # Draw
            node_sizes = [300 + 100 * G.degree(n) for n in G.nodes()]
            # Cap size
            node_sizes = [min(s, 1000) for s in node_sizes]

            nx.draw_networkx_nodes(G, pos, ax=ax, node_size=node_sizes, node_color='lightblue', alpha=0.9)
            nx.draw_networkx_edges(G, pos, ax=ax, edge_color='gray', alpha=0.5, arrows=True, arrowsize=10)
            
            # Labels
            labels = {n: n for n in G.nodes()}
            for n in labels:
                if len(labels[n]) > 15:
                    labels[n] = labels[n][:12] + "..."
            
            nx.draw_networkx_labels(G, pos, ax=ax, labels=labels, font_size=8, font_family="sans-serif")

            ax.set_axis_off()
            
            canvas = FigureCanvasTkAgg(fig, master=self.canvas_container)
            canvas.draw()
            
            toolbar_frame = ttk.Frame(self.canvas_container)
            toolbar_frame.pack(side="bottom", fill="x")
            toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
            toolbar.update()
            
            canvas.get_tk_widget().pack(fill="both", expand=True)

        except Exception as e:
            logger.error(f"Draw graph failed: {e}")
            ttk.Label(self.canvas_container, text=f"前端渲染出错: {e}").pack(expand=True)

    def save_dependency_graph(self):
        if not HAS_NETWORKX:
            messagebox.showinfo("提示", "未安装 networkx/matplotlib，无法保存图像。")
            return
        
        if not self.mods and not self.dependency_pairs:
             messagebox.showinfo("提示", "没有依赖数据可保存。请先进行分析。")
             return

        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG 图片", "*.png")])
        if not path:
            return
            
        try:
            plt.figure(figsize=(12, 8))
            G = nx.DiGraph()
            for mod in self.mods.keys():
                G.add_node(mod)
            for a, b in self.dependency_pairs:
                G.add_edge(a, b)
            
            # 使用简单的弹簧布局
            if hasattr(nx, 'spring_layout'):
                pos = nx.spring_layout(G)
                nx.draw(G, pos, with_labels=True, node_color='lightblue', edge_color='gray', node_size=500, font_size=8, arrows=True)
            else:
                nx.draw(G, with_labels=True)

            plt.title("MOD Dependency Graph")
            plt.savefig(path)
            plt.close()
            
            messagebox.showinfo("已保存", f"依赖图已保存到: {path}")
        except Exception as e:
            messagebox.showerror("保存失败", f"保存图表失败: {e}")

    def update_cause_chart(self):
        if not HAS_NETWORKX:  # Reusing mpl check
            for w in self.cause_canvas_container.winfo_children():
                w.destroy()
            ttk.Label(self.cause_canvas_container, text="缺少依赖: matplotlib，无法绘制图表").pack(expand=True)
            return
            
        # 清理旧图表
        for w in self.cause_canvas_container.winfo_children():
            w.destroy()
            
        if not self.cause_counts:
            ttk.Label(self.cause_canvas_container, text="暂无原因数据").pack(expand=True)
            return

        try:
            fig = plt.Figure(figsize=(5, 4), dpi=100)
            ax = fig.add_subplot(111)
            
            labels = [k for k, _ in self.cause_counts.most_common(8)]
            values = [v for _, v in self.cause_counts.most_common(8)]
            
            ax.pie(values, labels=labels, autopct='%1.1f%%', startangle=90)
            ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
            ax.set_title("崩溃暂因分布")

            canvas = FigureCanvasTkAgg(fig, master=self.cause_canvas_container)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)
        except Exception as e:
            logger.error(f"绘制原因图表失败: {e}")
            ttk.Label(self.cause_canvas_container, text=f"绘图出错: {e}").pack(expand=True)

    def view_history(self):
        try:
            if not os.path.exists(HISTORY_FILE):
                messagebox.showinfo("历史", "暂无历史记录。")
                return

            win = tk.Toplevel(self.root)
            win.title("分析历史")
            win.geometry("800x400")

            tree = ttk.Treeview(win, columns=("time", "summary", "path"), show="headings")
            tree.heading("time", text="时间")
            tree.column("time", width=150)
            tree.heading("summary", text="摘要")
            tree.column("summary", width=400)
            tree.heading("path", text="文件路径")
            tree.column("path", width=200)
            
            scrollbar = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            
            tree.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            # Load history
            with open(HISTORY_FILE, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                rows = list(reader)
                for row in reversed(rows):  # Newest first
                    if len(row) >= 3:
                        tree.insert("", "end", values=row[:3])
            
            def _on_dbl_click(event):
                item = tree.selection()
                if not item: return
                vals = tree.item(item[0], "values")
                if len(vals) >= 3 and os.path.exists(vals[2]):
                     self.detect_and_load_file(vals[2])
                     win.destroy()
            
            tree.bind("<Double-1>", _on_dbl_click)

        except Exception as e:
            messagebox.showerror("错误", f"无法读取历史记录: {e}")

    def import_mods(self):
        """导入并分析 Mods 文件夹"""
        folder = filedialog.askdirectory(title="选择 .minecraft/mods 文件夹")
        if not folder:
            return
            
        self.progress.pack(fill="x", padx=10, pady=(4, 6))
        self.progress.config(mode="indeterminate")
        self.progress.start(10)
        self.status_var.set("正在扫描 Mods 文件夹...")
        
        def _scan():
            try:
                mod_files = []
                for root, _, files in os.walk(folder):
                    for f in files:
                        if f.endswith(".jar"):
                            mod_files.append(f)
                
                # 简单解析文件名
                self.mods = defaultdict(set)
                for f in mod_files:
                    # Reuse pattern from extract logic
                    m = RegexCache.search(r"([a-zA-Z0-9_\-]+)-(\d[\w\.\-]+)\.jar", f)
                    if m:
                        mid = self._clean_modid(m.group(1))
                        if mid:
                            self.mods[mid].add(m.group(2))
                
                self.root.after(0, lambda: self.status_var.set(f"已导入 {len(self.mods)} 个模组"))
                self.root.after(0, lambda: messagebox.showinfo("导入完成", f"在文件夹中发现 {len(self.mods)} 个模组。"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("导入失败", str(e)))
            finally:
                self.root.after(0, self.progress.stop)
                self.root.after(0, lambda: self.progress.pack_forget())
        
        threading.Thread(target=_scan, daemon=True).start()

    def _toggle_tail(self):
        if self._tail_running:
            self._tail_running = False
            self._tail_btn_var.set("开始跟踪")
            self.status_var.set("日志跟踪已停止")
        else:
            if not self.file_path or not os.path.exists(self.file_path):
                 messagebox.showinfo("提示", "请先加载一个有效的本地日志文件。")
                 return
            
            self._tail_running = True
            self._tail_btn_var.set("停止跟踪")
            self.status_var.set("正在跟踪日志变化...")
            threading.Thread(target=self._tail_worker, daemon=True).start()

    def _tail_worker(self):
        try:
            with open(self.file_path, "r", encoding="utf-8", errors="ignore") as f:
                # Seek to end
                f.seek(0, 2)
                
                while self._tail_running:
                    line = f.readline()
                    if line:
                        self.root.after(0, lambda l=line: self._append_log_line(l))
                    else:
                        time.sleep(0.5)
        except Exception as e:
            logger.error(f"Tail error: {e}")
            self._tail_running = False
            self.root.after(0, lambda: self._tail_btn_var.set("开始跟踪(出错)"))

    def _append_log_line(self, line):
        self.log_text.config(state="normal")
        self.log_text.insert("end", line)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _on_tab_changed(self, event):
        # Lazy render charts
        try:
            id = self.bottom_notebook.select()
            if id == str(self.graph_tab):
                self.update_dependency_graph()
            elif id == str(self.cause_tab):
                self.update_cause_chart()
        except Exception:
            pass




