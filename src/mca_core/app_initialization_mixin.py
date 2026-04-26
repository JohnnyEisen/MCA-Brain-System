"""
初始化 Mixin 模块

提供 DLC 加载、Brain 初始化和检测器设置功能。

模块说明:
    本模块实现了应用程序初始化相关的功能，通过 Mixin 模式为主应用提供服务。
    
    主要组件:
        - InitializationMixin: 初始化逻辑 Mixin 类

功能列表:
    - DLC 异步加载
    - Brain AI 引擎延迟初始化
    - 检测器注册和设置
    - 事件总线订阅
    - UI 组件初始化
"""

from __future__ import annotations

import logging
import os
import threading
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from tkinter import Tk
    from mca_core.detectors import DetectorRegistry
    from mca_core.services.database import DatabaseManager

from mca_core.threading_utils import submit_task

try:
    from brain_system.core import BrainCore
    HAS_BRAIN: bool = True
except ImportError:
    HAS_BRAIN = False
    BrainCore = None

logger = logging.getLogger(__name__)


class InitializationMixin:
    """
    初始化逻辑 Mixin。
    
    提供应用程序初始化相关的功能，包括:
    - DLC 异步加载
    - Brain AI 引擎延迟初始化
    - 检测器注册和设置
    - 事件总线订阅
    - UI 组件初始化
    
    该 Mixin 假设宿主类具有以下属性:
        - brain: BrainCore AI 引擎实例
        - detector_registry: 检测器注册表
        - crash_pattern_learner: 崩溃模式学习器
        - container: 依赖注入容器
        - root: Tk 根窗口
        - ai_status_var: AI 状态变量 (可选)
        - brain_monitor: Brain 监视器控件 (可选)
        - main_notebook: 主笔记本控件 (可选)
    
    Attributes:
        _ai_init_started: AI 初始化是否已开始
        _brain_init_lock: Brain 初始化锁
        _brain_config_path: Brain 配置路径
    
    方法:
        - _load_dlcs_async: 异步加载 DLC
        - _start_ai_init_if_needed: 启动 AI 初始化
        - _setup_detectors: 设置检测器
    """
    
    brain: Any
    detector_registry: "DetectorRegistry"
    crash_pattern_learner: Any
    idle_trainer: Any
    diagnostic_engine: Any
    crash_pattern_lib: Any
    dependency_analyzer_cls: Any
    HAS_NEW_MODULES: bool
    event_bus: Any
    progress_reporter: Any
    task_executor: Any
    container: Any
    root: Any
    ai_status_var: Any
    brain_monitor: Any
    main_notebook: Any
    _ai_init_started: bool
    _brain_init_lock: threading.Lock
    _brain_config_path: str | None

    def _load_dlcs_async(self) -> None:
        """
        后台异步加载算力 DLC。
        
        按顺序加载以下 DLC:
        1. HardwareAcceleratorDLC - 硬件加速
        2. CodeBertDLC - 语义引擎
        3. NeuralNetworkOperatorsDLC - 神经网络算子
        4. NeuralWorkflowDLC - 工作流管理器
        5. DistributedComputingDLC - 分布式计算节点
        """
        if not self.brain:
            return
            
        logger.info("Starting background engine initialization...")
        
        if hasattr(self, 'ai_status_var') and self.ai_status_var:
            self.root.after(0, lambda: self.ai_status_var.set("Analysis: Loading..."))
        if hasattr(self, 'brain_monitor') and self.brain_monitor:
            self.root.after(0, lambda: self.brain_monitor.animate_loading())
        
        self._load_hardware_accelerator_dlc()
        self._load_codebert_dlc()
        self._load_neural_network_dlc()
        self._load_workflow_dlc()
        self._load_distributed_dlc()

    def _load_hardware_accelerator_dlc(self) -> None:
        """加载硬件加速器 DLC。"""
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

    def _load_codebert_dlc(self) -> None:
        """加载 CodeBERT 语义引擎 DLC。"""
        try:
            from dlcs.brain_dlc_codebert import CodeBertDLC
            bert_dlc = CodeBertDLC(self.brain)
            self.brain.register_dlc(bert_dlc)
            logger.info("Semantic Engine (CodeBERT) DLC 已挂载")
            
            if self.crash_pattern_learner and bert_dlc.provide_computational_units()["is_ready"]():
                units = bert_dlc.provide_computational_units()
                self.crash_pattern_learner.set_semantic_engine(
                    units["encode_text"], 
                    units["calculate_similarity"]
                )
                logger.info("分析模式切换: 深度语义理解 (CodeBERT)")
                if hasattr(self, 'ai_status_var') and self.ai_status_var:
                    self.root.after(
                        0, 
                        lambda: self.brain_monitor.set_status("Analysis: 语义模型已就绪") if hasattr(self, 'brain_monitor') and self.brain_monitor else None
                    )
        except ImportError as e:
            logger.warning(f"无法启用 CodeBERT (ImportError): {e}")
            if hasattr(self, 'ai_status_var') and self.ai_status_var:
                self.root.after(0, lambda: self.brain_monitor.set_status("Analysis: 仅规则模式") if hasattr(self, 'brain_monitor') and self.brain_monitor else None)
        except Exception as dlc_error:
            logger.warning(f"ML 引擎加载跳过: {dlc_error}")

    def _load_neural_network_dlc(self) -> None:
        """加载神经网络算子 DLC。"""
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

    def _load_workflow_dlc(self) -> None:
        """加载工作流管理器 DLC。"""
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

    def _load_distributed_dlc(self) -> None:
        """加载分布式计算节点 DLC。"""
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

    def _start_ai_init_if_needed(self) -> None:
        """
        启动 AI 引擎初始化（延迟加载）。
        
        使用双重检查锁定确保线程安全。
        """
        if not self.brain:
            if HAS_BRAIN and BrainCore is not None and getattr(self, '_brain_config_path', None):
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
        
        if hasattr(self, 'ai_status_var') and self.ai_status_var:
            try:
                self.ai_status_var.set("Analysis: 初始化中...")
            except Exception:
                pass
        
        submit_task(self._load_dlcs_async)

    def _setup_detectors(self) -> None:
        """
        注册所有可用的检测器。
        
        初始化以下组件:
        1. 检测器注册表
        2. 空闲训练器
        3. 配置加载
        4. 日志处理器
        5. 数据库文件
        6. 冲突数据库
        7. 模式学习器
        8. 诊断引擎
        9. 事件总线
        10. UI 组件
        """
        import tkinter.messagebox as msgbox
        from config.constants import BASE_DIR
        
        self._setup_detector_registry(msgbox)
        self._setup_idle_trainer(BASE_DIR)
        self._setup_config_loader()
        self._setup_log_handler(BASE_DIR)
        self._ensure_db_files()
        self._load_conflict_db()
        self._setup_pattern_learner(BASE_DIR)
        self._setup_diagnostic_modules(BASE_DIR)
        self._setup_event_system()
        self._finalize_ui_setup()

    def _setup_detector_registry(self, msgbox: Any) -> None:
        """
        设置检测器注册表。
        
        Args:
            msgbox: 消息框模块
        """
        self.detector_registry.load_builtins()
        
        loaded_count = len(self.detector_registry.list())
        if loaded_count == 0:
            msgbox.showwarning(
                "核心组件缺失",
                "未检测到任何故障诊断器！\n程序将无法诊断崩溃原因。"
            )

    def _setup_idle_trainer(self, base_dir: str) -> None:
        """
        设置空闲训练器。
        
        Args:
            base_dir: 基础目录
        """
        self.idle_trainer = None
        try:
            from mca_core.idle_trainer import IdleTrainer
            HAS_IDLE_TRAINER = True
        except Exception:
            HAS_IDLE_TRAINER = False
            
        if HAS_IDLE_TRAINER:
            self.idle_trainer = IdleTrainer(
                self.crash_pattern_learner,
                os.path.join(base_dir, "analysis_data", "auto_tests_idle")
            )
            self.idle_trainer.start()

    def _setup_config_loader(self) -> None:
        """设置配置加载器。"""
        try:
            self._load_config()
        except OSError:
            logger.error("加载配置失败")

    def _setup_log_handler(self, base_dir: str) -> None:
        """
        设置日志处理器。
        
        Args:
            base_dir: 基础目录
        """
        try:
            from logging.handlers import RotatingFileHandler
            log_path = os.path.join(base_dir, 'app.log')
            existing = any(
                isinstance(h, RotatingFileHandler) and 
                getattr(h, 'baseFilename', None) == os.path.abspath(log_path)
                for h in logger.handlers
            )
            if not existing:
                rh = RotatingFileHandler(
                    log_path,
                    maxBytes=1_000_000,
                    backupCount=5,
                    encoding='utf-8'
                )
                rh.setFormatter(
                    logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
                )
                logger.addHandler(rh)
        except Exception:
            logger.debug('无法创建 RotatingFileHandler')

    def _setup_pattern_learner(self, base_dir: str) -> None:
        """
        设置崩溃模式学习器。
        
        Args:
            base_dir: 基础目录
        """
        try:
            from mca_core.learning import CrashPatternLearner
            storage_path = os.path.join(base_dir, "analysis_data", "learned_patterns.json")
            self.crash_pattern_learner = CrashPatternLearner(storage_path)
        except Exception as e:
            logger.warning(f"无法初始化模式学习器: {e}")
            self.crash_pattern_learner = None

    def _setup_diagnostic_modules(self, base_dir: str) -> None:
        """
        设置诊断模块。
        
        Args:
            base_dir: 基础目录
        """
        self.diagnostic_engine = None
        self.crash_pattern_lib = None
        self.dependency_analyzer_cls = None
        
        try:
            from mca_core.diagnostic_engine import DiagnosticEngine
            from mca_core.crash_patterns import CrashPatternLibrary
            from mca_core.dependency_analyzer import DependencyAnalyzer
            
            self.diagnostic_engine = DiagnosticEngine(base_dir)
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

    def _setup_event_system(self) -> None:
        """设置事件系统。"""
        self._init_ui_components()
        self._create_log_area()

        from mca_core.events import EventBus, EventTypes
        from mca_core.progress import ProgressReporter
        from mca_core.task_executor import TaskExecutor
        
        self.event_bus = EventBus()
        self.progress_reporter = ProgressReporter()
        self.task_executor = TaskExecutor()
        
        self.event_bus.subscribe_batch([
            (EventTypes.ANALYSIS_START, self._on_analysis_start_event),
            (EventTypes.ANALYSIS_COMPLETE, self._on_analysis_complete_event),
            (EventTypes.ANALYSIS_ERROR, self._on_analysis_error_event),
            (EventTypes.ANALYSIS_PROGRESS, self._on_analysis_progress_event),
            (EventTypes.DETECTOR_COMPLETE, self._on_detector_complete_event),
        ])
        self.progress_reporter.subscribe(self._on_progress_report)

    def _finalize_ui_setup(self) -> None:
        """完成 UI 设置。"""
        self._center_window()
        self._apply_styles()

        self._graph_cache_key = None
        self._graph_rendered = False
        self._cancel_event = threading.Event()
        
        if hasattr(self, 'main_notebook') and self.main_notebook:
            try:
                self.main_notebook.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
            except Exception as e:
                logger.debug(f"绑定标签页切换事件失败: {e}")
            
        self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)

    def _ensure_db_files(self) -> None:
        """确保数据库文件存在。"""
        pass

    def _load_conflict_db(self) -> None:
        """加载冲突数据库。"""
        pass

    def _load_config(self) -> None:
        """加载配置文件。"""
        pass

    def _init_ui_components(self) -> None:
        """初始化 UI 组件。"""
        pass

    def _create_log_area(self) -> None:
        """创建日志区域。"""
        pass

    def _center_window(self) -> None:
        """居中窗口。"""
        pass

    def _apply_styles(self) -> None:
        """应用样式。"""
        pass

    def _on_tab_changed(self, event: Any) -> None:
        """处理标签页切换事件。"""
        pass

    def on_window_close(self) -> None:
        """处理窗口关闭事件。"""
        pass

    def _on_analysis_start_event(self, event: Any) -> None:
        """处理分析开始事件。"""
        pass

    def _on_analysis_complete_event(self, event: Any) -> None:
        """处理分析完成事件。"""
        pass

    def _on_analysis_error_event(self, event: Any) -> None:
        """处理分析错误事件。"""
        pass

    def _on_analysis_progress_event(self, event: Any) -> None:
        """处理分析进度事件。"""
        pass

    def _on_detector_complete_event(self, event: Any) -> None:
        """处理检测器完成事件。"""
        pass

    def _on_progress_report(self, value: float, message: str) -> None:
        """处理进度报告。"""
        pass
