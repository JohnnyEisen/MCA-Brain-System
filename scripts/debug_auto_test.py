
import sys
import os
import time
from collections import Counter
import threading

# Add root to sys.path
sys.path.insert(0, os.path.abspath("."))

from mca_core.app import MinecraftCrashAnalyzer
from tools.generate_mc_log import generate_batch, SCENARIOS
try:
    from tools.neural_adversary import NeuralAdversaryEngine
    HAS_NEURAL = True
except ImportError:
    HAS_NEURAL = False

# Mocking the UI parts since we are running in console
import tkinter as tk
from tkinter import ttk

class MockApp(MinecraftCrashAnalyzer):
    def __init__(self):
        # Skip super().__init__ which creates UI
        # Initialize only what's needed for analysis
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except:
            self.root = None # Headless
            
        self.crash_log = ""
        self.file_path = ""
        self.analysis_results = []
        self.mods = {}
        self.dependency_pairs = set()
        self.cause_counts = Counter()
        self.lock = threading.Lock()
        self.app_config = None
        self._log_cache_raw = None
        
        # Initialize subsystems
        from mca_core.detectors.registry import DetectorRegistry
        from mca_core.detectors import (
            OutOfMemoryDetector, JvmIssuesDetector, VersionConflictsDetector,
            DuplicateModsDetector, ModConflictsDetector, ShaderWorldConflictsDetector,
            MissingDependenciesDetector, LoaderDetector, MissingGeckoLibDetector,
            GeckoLibMoreDetector, GlErrorsDetector
        )
        
        self.detector_registry = DetectorRegistry()
        self.detector_registry.register(LoaderDetector())
        self.detector_registry.register(OutOfMemoryDetector())
        self.detector_registry.register(JvmIssuesDetector())
        self.detector_registry.register(MissingDependenciesDetector())
        self.detector_registry.register(VersionConflictsDetector())
        self.detector_registry.register(DuplicateModsDetector())
        self.detector_registry.register(ModConflictsDetector())
        self.detector_registry.register(ShaderWorldConflictsDetector())
        self.detector_registry.register(GlErrorsDetector())
        self.detector_registry.register(MissingGeckoLibDetector())
        self.detector_registry.register(GeckoLibMoreDetector())
        
        # Initialize Brain / Pattern Learner (Optional)
        self.crash_pattern_learner = None
        
        self.plugin_registry = type("MockPluginRegistry", (), {"list": lambda self: []})()
        self.HAS_NEW_MODULES = False
        self.brain = None
        self._analysis_cache = {}

    def _invalidate_log_cache(self):
        pass
        
    def _report_progress(self, val, msg):
        pass # print(f"[Progress] {val:.2f}: {msg}")

    # Helper from app.py
    def add_cause(self, cause_label: str):
        with self.lock:
            self.cause_counts[cause_label] += 1
            
    def _run_analysis_logic_public(self):
        return self._run_analysis_logic()

    def _detect_loader(self):
        txt = (self.crash_log or "").lower()
        if "neoforge" in txt: return "NeoForge"
        if "forge" in txt: return "Forge"
        if "fabric" in txt: return "Fabric"
        if "quilt" in txt: return "Quilt"
        return "Unknown"
        
    def _extract_mods(self):
        # Simplified extraction for tests
        pass
        
    def _build_precise_summary(self):
        pass
        
    def _clean_dependency_pairs(self):
        pass

def run_test_scenario(scenario_name, check_condition, desc):
    print(f"\n[{desc}] Generating '{scenario_name}' Log ...")
    out_dir = "debug_logs/auto_test_runs"
    os.makedirs(out_dir, exist_ok=True)
    
    # Use generate_batch
    summary = generate_batch(
        output_dir=out_dir,
        count=1,
        scenarios=[scenario_name],
        target_bytes=512*1024, 
        seed=None, # Random seed
        report_path=None
    )
    
    file_path = summary[0]["file"]
    with open(file_path, "r", encoding="utf-8") as f:
        log_text = f.read()
        
    app = MockApp()
    app.crash_log = log_text
    app.file_path = file_path
    
    start_t = time.time()
    app._run_analysis_logic_public()
    dur = time.time() - start_t
    
    print(f"   Analysis Time: {dur:.3f}s")
    print(f"   Causes Found: {dict(app.cause_counts)}")
    
    success = check_condition(app)
    status = "SUCCESS" if success else "FAILURE"
    print(f"-> {status}")
    return success

def test_oom():
    def check(app):
        return any("memory" in r.lower() for r in app.analysis_results) or app.cause_counts["内存不足"] > 0
    return run_test_scenario("oom", check, "OOM Detection")

def test_gl_error():
    def check(app):
        return any("gl" in r.lower() or "render" in r.lower() for r in app.analysis_results) or app.cause_counts["显卡/渲染"] > 0
    return run_test_scenario("gl_error", check, "OpenGL Error Detection")

def test_adversarial():
    # Only run if engine available? No, generate_batch handles fallback.
    def check(app):
        # Adversarial can produce anything, just check if it analyzed successfully (no crash in analyzer)
        return len(app.analysis_results) >= 0 
    
    print("\n[Neural Adversary] Testing AI-Generated Log...")
    if not HAS_NEURAL:
        print("   (Note: NeuralEngine not found, using simulation fallback)")
        
    return run_test_scenario("adversarial", check, "Adversarial Generator Integrity")

def run_all_tests():
    print("=== Starting Automated Test Suite ===")
    results = []
    results.append(test_oom())
    results.append(test_gl_error())
    results.append(test_adversarial())
    
    passed = sum(results)
    total = len(results)
    print("="*40)
    print(f"Total Tests: {total}")
    print(f"Passed:      {passed}")
    print(f"Result:      {'PASS' if passed==total else 'FAIL'}")
    print("="*40)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "all":
        run_all_tests()
    else:
        # Default run all for convenience
        run_all_tests()
