import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))
from mca_core.detectors.registry import DetectorRegistry
from mca_core.detectors.contracts import AnalysisContext
import threading

class DummyAnalyzer:
    def __init__(self):
        self.crash_log = "java.lang.OutOfMemoryError: Java heap space"
        self.analysis_results = []
        self.lock = threading.RLock()

analyzer = DummyAnalyzer()
registry = DetectorRegistry()
registry.load_builtins()

results = registry.run_all_parallel(analyzer)
for res in analyzer.analysis_results:
    print(res)

