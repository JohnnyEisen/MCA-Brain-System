"""初始化 Mixin - DLC加载/Brain初始化/检测器设置"""

from __future__ import annotations
import os
import threading
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from mca_core.threading_utils import submit_task

# Brain 系统可用性检查
try:
    from brain_system.core import BrainCore
    HAS_BRAIN = True
except ImportError:
    HAS_BRAIN = False
    BrainCore = None

logger = logging.getLogger(__name__)


class InitializationMixin:
    """Mixin for application initialization logic."""
    
    def _load_dlcs_async(self):
        """后台异步加载算力 DLC."""
        if not self.brain:
            return
            
        logger.info("Starting background engine initialization...")
        if hasattr(self, 'ai_status_var'):
            self.root.after(0, lambda: self.ai_status_var.set("Analysis: Loading..."))
            self.root.after(0, lambda: self.brain_monitor.animate_loading())
        
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

        try:
            from dlcs.brain_dlc_codebert import CodeBertDLC
            bert_dlc = CodeBertDLC(self.brain)
            self.brain.register_dlc(bert_dlc)
            logger.info("Semantic Engine (CodeBERT) DLC 已挂载")
            if self.crash_pattern_learner and bert_dlc.provide_computational_units()["is_ready"]():
                units = bert_dlc.provide_computational_units()
                self.crash_pattern_learner.set_semantic_engine(units["encode_text"], units["calculate_similarity"])
                logger.info("分析模式切换: 深度语义理解 (CodeBERT)")
                if hasattr(self, 'ai_status_var'):
                    self.root.after(0, lambda: self.brain_monitor.set_status("Analysis: 语义模型已就绪"))
        except ImportError as e:
            logger.warning(f"无法启用 CodeBERT (ImportError): {e}")
            if hasattr(self, 'ai_status_var'):
                self.root.after(0, lambda: self.brain_monitor.set_status("Analysis: 仅规则模式"))
        except Exception as dlc_error:
            logger.warning(f"ML 引擎加载跳过: {dlc_error}")

        try:
            try:
                from brain_system.dlcs.brain_dlc_nn import NeuralNetworkOperatorsDLC
            except ImportError:
                from dlcs.brain_dlc_nn import NeuralNetworkOperatorsDLC
            nn_dlc = NeuralNetworkOperatorsDLC(self.brain)
            self.brain.register_dlc(nn_dlc)
            logger.info("DLC 已挂载: 神经网络算子 (Neural Ops)")
        except Exception as dlc_error:
            logger.warning(f"DLC 加载因错跳过: {dlc_error}")

        try:
            try:
                from brain_system.dlcs.brain_dlc_workflow import NeuralWorkflowDLC
            except ImportError:
                from dlcs.brain_dlc_workflow import NeuralWorkflowDLC
            wf_dlc = NeuralWorkflowDLC(self.brain)
            self.brain.register_dlc(wf_dlc)
            logger.info("DLC 已挂载: 工作流管理器")
        except Exception as dlc_error:
            logger.warning(f"工作流 DLC 加载错误: {dlc_error}")

        try:
            try:
                from brain_system.dlcs.brain_dlc_distributed import DistributedComputingDLC
            except ImportError:
                from dlcs.brain_dlc_distributed import DistributedComputingDLC
            dist_dlc = DistributedComputingDLC(self.brain)
            self.brain.register_dlc(dist_dlc)
            dist_dlc.start_workers(num_workers=max(2, os.cpu_count() or 2))
            logger.info("DLC 已挂载: 分布式计算节点")
        except Exception as dlc_error:
            logger.warning(f"分布式 DLC 初始化失败: {dlc_error}")

    def _start_ai_init_if_needed(self):
        # 延迟初始化 BrainCore
        if not self.brain:
            # 尝试创建 BrainCore
            if HAS_BRAIN and getattr(self, '_brain_config_path', None):
                try:
                    self.brain = BrainCore(config_path=self._brain_config_path)
                    logger.info("BrainCore 延迟初始化完成")
                except Exception as e:
                    logger.warning(f"BrainCore 初始化失败: {e}")
                    self.brain = None
                    return
            else:
                return
        
        if getattr(self, "_ai_init_started", False):
            return
        lock = getattr(self, "_brain_init_lock", None)
        if lock:
            with lock:
                if self._ai_init_started:
                    return
                self._ai_init_started = True
        else:
            self._ai_init_started = True
        try:
            if hasattr(self, 'ai_status_var'):
                self.ai_status_var.set("Analysis: 初始化中...")
        except Exception:
            pass
        submit_task(self._load_dlcs_async)

    def _setup_detectors(self):
        """注册所有可用的检测器"""
        import tkinter.messagebox as msgbox
        from config.constants import BASE_DIR
        
        self.detector_registry.load_builtins()
        
        loaded_count = len(self.detector_registry.list())
        if loaded_count == 0:
            msgbox.showwarning("核心组件缺失", "未检测到任何故障诊断器！\n程序将无法诊断崩溃原因。")
        
        self.idle_trainer = None
        try:
            from mca_core.idle_trainer import IdleTrainer
            HAS_IDLE_TRAINER = True
        except Exception:
            HAS_IDLE_TRAINER = False
            
        if HAS_IDLE_TRAINER:
            self.idle_trainer = IdleTrainer(self.crash_pattern_learner, os.path.join(BASE_DIR, "analysis_data", "auto_tests_idle"))
            self.idle_trainer.start()

        try:
            self._load_config()
        except OSError:
            logger.error("加载配置失败")

        try:
            from logging.handlers import RotatingFileHandler
            log_path = os.path.join(BASE_DIR, 'app.log')
            existing = any(isinstance(h, RotatingFileHandler) and getattr(h, 'baseFilename', None) == os.path.abspath(log_path) for h in logger.handlers)
            if not existing:
                rh = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=5, encoding='utf-8')
                rh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
                logger.addHandler(rh)
        except Exception:
            logger.debug('无法创建 RotatingFileHandler')

        self._ensure_db_files()
        self._load_conflict_db()

        try:
            from mca_core.learning import CrashPatternLearner
            storage_path = os.path.join(BASE_DIR, "analysis_data", "learned_patterns.json")
            self.crash_pattern_learner = CrashPatternLearner(storage_path)
        except Exception as e:
            logger.warning(f"无法初始化模式学习器: {e}")
            self.crash_pattern_learner = None

        self.diagnostic_engine = None
        self.crash_pattern_lib = None
        self.dependency_analyzer_cls = None
        try:
            from mca_core.diagnostic_engine import DiagnosticEngine
            from mca_core.crash_patterns import CrashPatternLibrary
            from mca_core.dependency_analyzer import DependencyAnalyzer
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

        self._init_ui_components()
        self._create_log_area()

        from mca_core.events import EventBus, EventTypes
        from mca_core.progress import ProgressReporter
        from mca_core.task_executor import TaskExecutor
        
        self.event_bus = EventBus()
        self.progress_reporter = ProgressReporter()
        self.task_executor = TaskExecutor()
        self.event_bus.subscribe(EventTypes.ANALYSIS_START, self._on_analysis_start_event)
        self.event_bus.subscribe(EventTypes.ANALYSIS_COMPLETE, self._on_analysis_complete_event)
        self.event_bus.subscribe(EventTypes.ANALYSIS_ERROR, self._on_analysis_error_event)
        self.event_bus.subscribe(EventTypes.ANALYSIS_PROGRESS, self._on_analysis_progress_event)
        self.event_bus.subscribe(EventTypes.DETECTOR_COMPLETE, self._on_detector_complete_event)
        self.progress_reporter.subscribe(self._on_progress_report)

        self._center_window()
        self._apply_styles()

        self._graph_cache_key = None
        self._graph_rendered = False
        self._cancel_event = threading.Event()
        try:
            self.main_notebook.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        except Exception as e:
            logger.debug(f"绑定标签页切换事件失败: {e}")
            
        self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)
