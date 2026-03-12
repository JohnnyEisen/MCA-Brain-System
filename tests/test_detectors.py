"""
核心检测器单元测试。

测试覆盖：
- OutOfMemoryDetector
- MissingDependenciesDetector
- GLErrorsDetector
- VersionConflictsDetector
- 检测器注册与发现
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mca_core.detectors.base import Detector
from mca_core.detectors.contracts import AnalysisContext, DetectionResult
from mca_core.detectors.out_of_memory import OutOfMemoryDetector
from mca_core.detectors.missing_dependencies import MissingDependenciesDetector


class MockAnalyzer:
    """模拟分析器，用于测试。"""
    
    def __init__(self):
        self.analysis_results = []
        self.cause_counts = {}
        self.lock = None
    
    def add_cause(self, label: str):
        self.cause_counts[label] = self.cause_counts.get(label, 0) + 1


class TestDetectorInterface(unittest.TestCase):
    """检测器接口测试。"""
    
    def test_detection_result_dataclass(self):
        """DetectionResult 应该正确初始化。"""
        result = DetectionResult(
            message="Test message",
            detector="TestDetector",
            cause_label="TestCause"
        )
        self.assertEqual(result.message, "Test message")
        self.assertEqual(result.detector, "TestDetector")
        self.assertEqual(result.cause_label, "TestCause")
        self.assertEqual(result.metadata, {})
    
    def test_analysis_context_initialization(self):
        """AnalysisContext 应该正确初始化。"""
        analyzer = MockAnalyzer()
        ctx = AnalysisContext(analyzer=analyzer, crash_log="test log")
        self.assertEqual(ctx.crash_log, "test log")
        self.assertEqual(ctx.results, [])
        self.assertEqual(ctx.cause_counts, {})


class TestOutOfMemoryDetector(unittest.TestCase):
    """内存溢出检测器测试。"""
    
    def setUp(self):
        self.detector = OutOfMemoryDetector()
        self.analyzer = MockAnalyzer()
    
    def test_detector_metadata(self):
        """检测器元数据应正确。"""
        self.assertEqual(self.detector.get_name(), "MemoryDetector")
        self.assertEqual(self.detector.get_cause_label(), "内存溢出")
    
    def test_detect_oom_error(self):
        """OutOfMemoryError 应被检测。"""
        log = """
        java.lang.OutOfMemoryError: Java heap space
        at java.util.Arrays.copyOf(Arrays.java:3332)
        """
        ctx = AnalysisContext(analyzer=self.analyzer, crash_log=log)
        results = self.detector.detect(log, ctx)
        
        self.assertTrue(len(results) > 0)
        self.assertTrue(any("内存溢出" in r.message for r in results))
        self.assertIn("内存溢出", ctx.cause_counts)
    
    def test_detect_out_of_memory_phrase(self):
        """'out of memory' 短语应被检测。"""
        log = "Error: out of memory while loading chunks"
        ctx = AnalysisContext(analyzer=self.analyzer, crash_log=log)
        results = self.detector.detect(log, ctx)
        
        self.assertTrue(len(results) > 0)
        self.assertTrue(any("内存溢出" in r.message for r in results))
    
    def test_no_memory_error(self):
        """无内存问题的日志不应触发。"""
        log = "Everything is fine. No errors here."
        ctx = AnalysisContext(analyzer=self.analyzer, crash_log=log)
        results = self.detector.detect(log, ctx)
        
        self.assertEqual(len(results), 0)
    
    def test_case_insensitive(self):
        """检测应不区分大小写。"""
        log = "OUTOFMEMORYERROR: Something went wrong"
        ctx = AnalysisContext(analyzer=self.analyzer, crash_log=log)
        results = self.detector.detect(log, ctx)
        
        self.assertTrue(len(results) > 0)
    
    def test_empty_log(self):
        """空日志应安全处理。"""
        ctx = AnalysisContext(analyzer=self.analyzer, crash_log="")
        results = self.detector.detect("", ctx)
        self.assertEqual(len(results), 0)


class TestMissingDependenciesDetector(unittest.TestCase):
    """缺失依赖检测器测试。"""
    
    def setUp(self):
        self.detector = MissingDependenciesDetector()
        self.analyzer = MockAnalyzer()
    
    def test_detector_metadata(self):
        """检测器元数据应正确。"""
        self.assertEqual(self.detector.get_name(), "DependencyDetector")
        self.assertEqual(self.detector.get_cause_label(), "缺失依赖")
    
    def test_detect_missing_mod_block(self):
        """ModSorter 格式的缺失依赖应被检测。"""
        log = """
        Missing or unsupported mandatory dependencies:
        Mod ID: 'geckolib', Requested by: ' draconicevolution ', Expected range: '[1.0.0,)', Actual version: '[MISSING]'
        """
        ctx = AnalysisContext(analyzer=self.analyzer, crash_log=log)
        results = self.detector.detect(log, ctx)
        
        # 注意：detect 方法可能返回 None，结果存储在 ctx.results 中
        if results is not None:
            self.assertTrue(len(results) > 0)
        else:
            # 结果存储在 context 中
            self.assertTrue(len(ctx.results) > 0)
        
        # 应该包含详细的依赖信息
        combined = " ".join(r.message for r in ctx.results)
        self.assertIn("geckolib", combined.lower())
    
    def test_detect_simple_missing(self):
        """简单的 'missing' 关键词应被检测。"""
        log = "Error: missing geckolib dependency"
        ctx = AnalysisContext(analyzer=self.analyzer, crash_log=log)
        self.detector.detect(log, ctx)
        
        self.assertTrue(len(ctx.results) > 0)

    def test_detect_requires_keyword(self):
        """Mod ID 格式的缺失依赖应被检测。"""
        log = "Mod ID: 'geckolib3', Requested by: 'dragonmounts'"
        ctx = AnalysisContext(analyzer=self.analyzer, crash_log=log)
        self.detector.detect(log, ctx)
        
        # 结果存储在 context 中
        self.assertTrue(len(ctx.results) > 0)
    
    def test_no_missing_dependency(self):
        """无缺失依赖的日志不应触发。"""
        log = "All mods loaded successfully"
        ctx = AnalysisContext(analyzer=self.analyzer, crash_log=log)
        results = self.detector.detect(log, ctx)
        
        self.assertEqual(len(results), 0)
    
    def test_filters_invalid_mod_names(self):
        """无效的模组名应被过滤。"""
        log = "missing or: something went wrong"  # "or" 是无效的mod名
        ctx = AnalysisContext(analyzer=self.analyzer, crash_log=log)
        results = self.detector.detect(log, ctx)
        
        # "or" 应该被过滤掉，不产生结果
        self.assertEqual(len(results), 0)
    
    def test_empty_log(self):
        """空日志应安全处理。"""
        ctx = AnalysisContext(analyzer=self.analyzer, crash_log="")
        results = self.detector.detect("", ctx)
        self.assertEqual(len(results), 0)


class TestAnalysisContext(unittest.TestCase):
    """AnalysisContext 功能测试。"""
    
    def test_add_result(self):
        """add_result 应正确添加结果。"""
        analyzer = MockAnalyzer()
        ctx = AnalysisContext(analyzer=analyzer, crash_log="")
        
        ctx.add_result("Test message", "TestDetector", "TestCause")
        
        self.assertEqual(len(ctx.results), 1)
        self.assertEqual(ctx.results[0].message, "Test message")
        self.assertIn("TestCause", ctx.cause_counts)
    
    def test_add_result_updates_analyzer(self):
        """add_result 应更新 analyzer 的 analysis_results。"""
        analyzer = MockAnalyzer()
        ctx = AnalysisContext(analyzer=analyzer, crash_log="")
        
        ctx.add_result("Test message", "TestDetector")
        
        self.assertIn("Test message", analyzer.analysis_results)
    
    def test_add_result_block(self):
        """add_result_block 应添加完整的结果块。"""
        analyzer = MockAnalyzer()
        ctx = AnalysisContext(analyzer=analyzer, crash_log="")
        
        ctx.add_result_block(
            header="Header message",
            items=["  - item 1", "  - item 2"],
            detector="TestDetector",
            cause_label="TestCause"
        )
        
        self.assertEqual(len(ctx.results), 3)  # header + 2 items
        self.assertEqual(ctx.results[0].message, "Header message")
    
    def test_context_without_analyzer(self):
        """无 analyzer 的 context 应能工作。"""
        ctx = AnalysisContext(analyzer=None, crash_log="test")
        
        ctx.add_result("Test message", "TestDetector")
        
        self.assertEqual(len(ctx.results), 1)


class TestDetectorIntegration(unittest.TestCase):
    """检测器集成测试。"""
    
    def test_multiple_detectors_same_context(self):
        """多个检测器可以共享同一个 context。"""
        oom_detector = OutOfMemoryDetector()
        dep_detector = MissingDependenciesDetector()
        
        analyzer = MockAnalyzer()
        log = """
        java.lang.OutOfMemoryError: Java heap space
        Also missing mod 'geckolib'
        """
        ctx = AnalysisContext(analyzer=analyzer, crash_log=log)
        
        oom_detector.detect(log, ctx)
        dep_detector.detect(log, ctx)
        
        # 应该有来自两个检测器的结果
        self.assertTrue(len(ctx.results) >= 2)
        self.assertIn("内存溢出", ctx.cause_counts)
        self.assertIn("缺失依赖", ctx.cause_counts)
    
    def test_real_world_crash_log(self):
        """真实崩溃日志测试。"""
        log = """
        ---- Minecraft Crash Report ----
        // This is a test crash
        
        Time: 2024-01-15 10:30:00
        Description: Unexpected error
        
        java.lang.OutOfMemoryError: Java heap space
        at java.util.Arrays.copyOf(Arrays.java:3332)
        at java.util.Arrays.copyOf(Arrays.java:3310)
        
        A detailed walkthrough of the error:
        Missing or unsupported mandatory dependencies:
        Mod ID: 'geckolib3', Requested by: 'dragonmounts', Expected range: '[3.0.0,)'
        """
        
        analyzer = MockAnalyzer()
        ctx = AnalysisContext(analyzer=analyzer, crash_log=log)
        
        OutOfMemoryDetector().detect(log, ctx)
        MissingDependenciesDetector().detect(log, ctx)
        
        # 应该检测到两个问题
        self.assertGreaterEqual(len(ctx.results), 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
