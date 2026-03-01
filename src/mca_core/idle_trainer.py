
import threading
import time
import os
import psutil
import logging
import random
from datetime import datetime, timedelta
from collections import Counter, defaultdict

try:
    import GPUtil
except ImportError:
    GPUtil = None

from tools.generate_mc_log import generate_batch, SCENARIOS
from mca_core.detectors.registry import DetectorRegistry
from mca_core.file_io import read_text_limited, read_text_head
from config.constants import LAB_HEAD_READ_SIZE

logger = logging.getLogger(__name__)

class HeadlessAnalyzer:
    """A minimal analyzer for background training that doesn't touch UI."""
    def __init__(self, learner, max_bytes: int = LAB_HEAD_READ_SIZE, head_only: bool = False):
        self.crash_pattern_learner = learner 
        self.crash_log = ""
        self.file_path = ""
        self.analysis_results = []
        self.cause_counts = Counter()
        # 使用 RLock，避免 AnalysisContext.add_result 内部调用 add_cause 时二次加锁死锁
        self.lock = threading.RLock()
        self.max_bytes = max_bytes
        self.head_only = head_only
        
        # Mimic App Structure for Detectors
        self.detector_registry = DetectorRegistry()
        # Register all core detectors (Auto-discovered)
        self.detector_registry.load_builtins()
        
        self.brain = None
        self.event_bus = None
        self.HAS_NEW_MODULES = False
        self.mods = defaultdict(set)
        self.dependency_pairs = set()

    def add_cause(self, label):
        with self.lock:
            self.cause_counts[label] += 1
            
    def _detect_loader(self):
        txt = (self.crash_log or "").lower()
        if "neoforge" in txt: return "NeoForge"
        if "forge" in txt: return "Forge"
        if "fabric" in txt: return "Fabric"
        if "quilt" in txt: return "Quilt"
        return "Unknown"

    def _extract_mods(self):
        # Full extraction logic is complex and relies on RegexCache. 
        # For idle training, we assume generated logs are structurally sound 
        # but if we want version conflict detection, we need basic extraction.
        # Here we do a simplified pass if needed, or rely on detectors using raw text.
        pass

    def _extract_dependency_pairs(self):
        self.dependency_pairs = set()

    def run_cycle(self, log_path):
        try:
            if self.head_only:
                self.crash_log = read_text_head(log_path, max_bytes=self.max_bytes)
            else:
                self.crash_log = read_text_limited(log_path, max_bytes=self.max_bytes)
            self.file_path = log_path
            self.analysis_results = []
            self.cause_counts = Counter()
            
            self._detect_loader()
            self._extract_mods() 
            self._extract_dependency_pairs()
            
            # 优化：在 Headless 模式（通常用于并行批量处理）下，应该避免使用嵌套线程池。
            # 文件级已经并行了，检测器级应保持串行以减少上下文切换和竞争。
            # Use run_all() instead of run_all_parallel()
            self.detector_registry.run_all(self)
            
            # Deduplicate
            self.analysis_results = list(dict.fromkeys(self.analysis_results))
            
            # Learn
            if self.crash_pattern_learner and self.analysis_results:
                self.crash_pattern_learner.learn_from_crash(self.crash_log, self.analysis_results)
                return True
        except Exception as e:
            logger.error(f"Headless Cycle Error: {e}")
        return False

class IdleTrainer:
    def __init__(self, learner, output_dir):
        self.learner = learner
        self.output_dir = output_dir
        self.analyzer = HeadlessAnalyzer(learner)
        self.running = False
        self.paused = False
        self.thread = None
        self.stop_event = threading.Event()
        
        # Default Config
        self.enabled = False
        self.duration_hours = 1.0
        self.max_cpu = 30
        self.max_ram = 80
        self.max_gpu = 30
        self.trained_count = 0
        self._session_deadline = None
        self._session_active = False
        
    def start(self):
        if self.running: return
        self.running = True
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._worker, daemon=True, name="IdleTrainer")
        self.thread.start()
        
    def stop(self):
        self.running = False
        self.stop_event.set()

    def _is_resource_ok(self):
        try:
            if psutil.cpu_percent(interval=0.1) > self.max_cpu: return False
            if psutil.virtual_memory().percent > self.max_ram: return False
            if GPUtil:
                gpus = GPUtil.getGPUs()
                if gpus and max(g.load * 100 for g in gpus) > self.max_gpu: return False
        except: 
            pass
        return True

    def _worker(self):
        # Low Priority
        try:
            p = psutil.Process()
            if psutil.WINDOWS:
                p.nice(psutil.IDLE_PRIORITY_CLASS)
            else:
                p.nice(19)
        except:
            pass
            
        while not self.stop_event.is_set():
            if not self.enabled:
                if self._session_active:
                    self._session_active = False
                    self._session_deadline = None
                time.sleep(2)
                continue

            if self._is_resource_ok() and not self.paused:
                try:
                    now = datetime.now()
                    if not self._session_active:
                        duration = max(float(self.duration_hours), 0.1)
                        self._session_deadline = now + timedelta(hours=duration)
                        self._session_active = True

                    if self._session_deadline and now >= self._session_deadline:
                        # Session finished, stop training until user re-enables
                        self._session_active = False
                        self.enabled = False
                        time.sleep(5)
                        continue

                    # Generate 1 log
                    scenario = random.choice(list(SCENARIOS.keys()))
                    summary = generate_batch(
                        output_dir=self.output_dir,
                        target_bytes=512*1024, # Small logs for fast training
                        seed=None,
                        scenarios=[scenario],
                        count=1,
                        report_path=None
                    )
                    
                    if summary:
                        fpath = summary[0]["file"]
                        success = self.analyzer.run_cycle(fpath)
                        if success:
                            self.trained_count += 1
                        
                        # Cleanup
                        try:
                            if os.path.exists(fpath):
                                os.remove(fpath)
                        except: pass
                        
                    # Sleep a bit to yield CPU
                    time.sleep(1) 
                except Exception as e:
                    logger.error(f"Trainer loop error: {e}")
                    time.sleep(5)
            else:
                # Wait longer if not in idle state
                time.sleep(10)

