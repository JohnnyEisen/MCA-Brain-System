"""
MCA Brain System 核心单元测试套件

合并内容:
- 文件 I/O 模块测试 (test_file_io.py)
- 正则缓存测试 (test_regex_cache.py)
- 分析管道测试 (test_pipeline.py)
- 规则引擎测试 (test_rules.py)
- 辅助函数测试 (test_helpers.py)
- 检测器注册表测试 (test_registry.py)
"""

import os
import re
import sys
import tempfile
import unittest
from dataclasses import dataclass
from typing import List, Optional, Protocol
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mca_core.file_io import (
    read_text_stream, read_text_limited, read_text_head, iter_lines
)
from mca_core.regex_cache import RegexCache
from mca_core.pipeline import AnalysisResult, ConfigurableAnalysisPipeline
from mca_core.rules import DetectionRule, RuleEngine
from mca_core.detectors.registry import DetectorRegistry
from mca_core.detectors.base import Detector
from mca_core.detectors.contracts import AnalysisContext
from utils.helpers import (
    mca_clean_modid, mca_levenshtein, mca_normalize_modid
)


# =============================================================================
# 文件 I/O 测试
# =============================================================================

class TestReadTextStream(unittest.TestCase):
    """分块流式读取测试。"""

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("")
            path = f.name
        try:
            chunks = list(read_text_stream(path))
            self.assertEqual(chunks, [])
        finally:
            os.unlink(path)

    def test_small_file(self):
        content = "Hello, World!"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            path = f.name
        try:
            result = "".join(read_text_stream(path))
            self.assertEqual(result, content)
        finally:
            os.unlink(path)

    def test_large_file_chunked(self):
        chunk_size = 100
        content = "A" * 500
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            path = f.name
        try:
            chunks = list(read_text_stream(path, chunk_size=chunk_size))
            self.assertGreater(len(chunks), 1)
            self.assertEqual("".join(chunks), content)
        finally:
            os.unlink(path)

    def test_unicode_content(self):
        content = "中文测试 日本語 한국어"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            path = f.name
        try:
            result = "".join(read_text_stream(path))
            self.assertEqual(result, content)
        finally:
            os.unlink(path)


class TestReadTextLimited(unittest.TestCase):
    """限制大小读取测试。"""

    def test_small_file_full_read(self):
        content = "Small content"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            path = f.name
        try:
            result = read_text_limited(path, max_bytes=1024)
            self.assertEqual(result, content)
        finally:
            os.unlink(path)

    def test_large_file_truncated(self):
        max_bytes = 100
        content = "A" * 1000
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            path = f.name
        try:
            result = read_text_limited(path, max_bytes=max_bytes)
            self.assertIn("TRUNCATED", result)
        finally:
            os.unlink(path)

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("")
            path = f.name
        try:
            result = read_text_limited(path)
            self.assertEqual(result, "")
        finally:
            os.unlink(path)


class TestReadTextHead(unittest.TestCase):
    """头部读取测试。"""

    def test_read_head(self):
        content = "A" * 1000
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            path = f.name
        try:
            result = read_text_head(path, max_bytes=100)
            self.assertEqual(len(result), 100)
        finally:
            os.unlink(path)

    def test_nonexistent_file(self):
        result = read_text_head("/nonexistent/path/file.txt")
        self.assertEqual(result, "")


class TestIterLines(unittest.TestCase):
    """行迭代器测试。"""

    def test_iterate_lines(self):
        content = "Line 1\nLine 2\nLine 3"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            path = f.name
        try:
            lines = list(iter_lines(path))
            self.assertEqual(len(lines), 3)
        finally:
            os.unlink(path)


# =============================================================================
# 正则缓存测试
# =============================================================================

class TestRegexCacheGet(unittest.TestCase):
    """模式获取测试。"""

    def setUp(self):
        RegexCache._cache = {}

    def test_compile_and_cache(self):
        pattern = r'\d+'
        compiled = RegexCache.get(pattern)
        self.assertIsInstance(compiled, type(re.compile('')))
        self.assertIn((pattern, 0), RegexCache._cache)

    def test_cache_hit(self):
        pattern = r'\w+'
        first = RegexCache.get(pattern)
        second = RegexCache.get(pattern)
        self.assertIs(first, second)

    def test_different_flags(self):
        pattern = r'test'
        case_sensitive = RegexCache.get(pattern, flags=0)
        case_insensitive = RegexCache.get(pattern, flags=re.IGNORECASE)
        self.assertIsNot(case_sensitive, case_insensitive)


class TestRegexCacheSearch(unittest.TestCase):
    """搜索方法测试。"""

    def setUp(self):
        RegexCache._cache = {}

    def test_search_match(self):
        text = "Hello 123 World"
        match = RegexCache.search(r'\d+', text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(), "123")

    def test_search_no_match(self):
        text = "Hello World"
        match = RegexCache.search(r'\d+', text)
        self.assertIsNone(match)


class TestRegexCacheFindall(unittest.TestCase):
    """查找全部方法测试。"""

    def setUp(self):
        RegexCache._cache = {}

    def test_findall_multiple(self):
        text = "a1b2c3d4"
        matches = RegexCache.findall(r'\d', text)
        self.assertEqual(matches, ['1', '2', '3', '4'])

    def test_findall_no_match(self):
        text = "abcdef"
        matches = RegexCache.findall(r'\d', text)
        self.assertEqual(matches, [])


# =============================================================================
# 分析管道测试
# =============================================================================

class MockAnalysisStep:
    """模拟分析步骤。"""
    def __init__(self, name: str, should_run: bool = True, result: Optional[AnalysisResult] = None):
        self.name = name
        self._should_run = should_run
        self._result = result or AnalysisResult()
        self.execute_count = 0

    def should_execute(self, context) -> bool:
        return self._should_run

    def execute(self, crash_log: str, context) -> AnalysisResult:
        self.execute_count += 1
        return self._result


class TestAnalysisResult(unittest.TestCase):
    """AnalysisResult 数据类测试。"""

    def test_default_empty(self):
        result = AnalysisResult()
        self.assertEqual(result.entries, [])

    def test_merge(self):
        result1 = AnalysisResult(entries=["a"])
        result2 = AnalysisResult(entries=["b", "c"])
        result1.merge(result2)
        self.assertEqual(result1.entries, ["a", "b", "c"])


class TestConfigurableAnalysisPipeline(unittest.TestCase):
    """可配置分析管道测试。"""

    def test_empty_pipeline(self):
        pipeline = ConfigurableAnalysisPipeline(steps=[])
        result = pipeline.execute("crash log", {})
        self.assertEqual(result.entries, [])

    def test_single_step(self):
        step = MockAnalysisStep("step1", result=AnalysisResult(entries=["result1"]))
        pipeline = ConfigurableAnalysisPipeline(steps=[step])
        result = pipeline.execute("crash log", {})
        self.assertEqual(result.entries, ["result1"])

    def test_step_condition_skip(self):
        step1 = MockAnalysisStep("step1", should_run=True, result=AnalysisResult(entries=["a"]))
        step2 = MockAnalysisStep("step2", should_run=False, result=AnalysisResult(entries=["b"]))
        step3 = MockAnalysisStep("step3", should_run=True, result=AnalysisResult(entries=["c"]))
        pipeline = ConfigurableAnalysisPipeline(steps=[step1, step2, step3])
        result = pipeline.execute("crash log", {})
        self.assertEqual(result.entries, ["a", "c"])


# =============================================================================
# 规则引擎测试
# =============================================================================

class TestDetectionRule(unittest.TestCase):
    """检测规则测试。"""

    def test_matches_found(self):
        rule = DetectionRule(name="test", keyword="error", message="Error found")
        self.assertTrue(rule.matches("An error occurred"))
        self.assertTrue(rule.matches("ERROR in log"))

    def test_matches_not_found(self):
        rule = DetectionRule(name="test", keyword="crash", message="Crash found")
        self.assertFalse(rule.matches("Everything is fine"))

    def test_matches_empty_log(self):
        rule = DetectionRule(name="test", keyword="error", message="Error")
        self.assertFalse(rule.matches(""))


class TestRuleEngine(unittest.TestCase):
    """规则引擎测试。"""

    def setUp(self):
        self.engine = RuleEngine()

    def test_empty_engine(self):
        results = self.engine.evaluate("Some log")
        self.assertEqual(results, [])

    def test_single_rule_match(self):
        rule = DetectionRule(name="r1", keyword="error", message="Error found")
        self.engine.add_rule(rule)
        results = self.engine.evaluate("An error occurred")
        self.assertEqual(len(results), 1)

    def test_multiple_rules(self):
        self.engine.add_rule(DetectionRule(name="r1", keyword="error", message="Error"))
        self.engine.add_rule(DetectionRule(name="r2", keyword="warning", message="Warning"))
        results = self.engine.evaluate("error and warning detected")
        self.assertEqual(len(results), 2)


# =============================================================================
# 辅助函数测试
# =============================================================================

class TestMcaCleanModid(unittest.TestCase):
    """模组ID清理测试。"""

    def test_valid_modid(self):
        self.assertEqual(mca_clean_modid("geckolib"), "geckolib")
        self.assertEqual(mca_clean_modid("create"), "create")

    def test_remove_special_chars(self):
        self.assertEqual(mca_clean_modid("gecko-lib"), "gecko-lib")
        self.assertEqual(mca_clean_modid("mod_name"), "mod_name")
        self.assertEqual(mca_clean_modid("gecko@lib"), "geckolib")

    def test_empty_input(self):
        self.assertIsNone(mca_clean_modid(""))
        self.assertIsNone(mca_clean_modid(None))

    def test_ignored_words(self):
        self.assertIsNone(mca_clean_modid("mod"))
        self.assertIsNone(mca_clean_modid("unknown"))

    def test_too_short(self):
        self.assertIsNone(mca_clean_modid("a"))


class TestMcaLevenshtein(unittest.TestCase):
    """编辑距离测试。"""

    def test_identical_strings(self):
        self.assertEqual(mca_levenshtein("test", "test"), 0)

    def test_empty_string(self):
        self.assertEqual(mca_levenshtein("", "abc"), 3)
        self.assertEqual(mca_levenshtein("abc", ""), 3)

    def test_single_char_diff(self):
        self.assertEqual(mca_levenshtein("cat", "bat"), 1)

    def test_complex_case(self):
        self.assertEqual(mca_levenshtein("kitten", "sitting"), 3)


class TestMcaNormalizeModid(unittest.TestCase):
    """模组ID规范化测试。"""

    def setUp(self):
        self.mods_keys = ["geckolib", "create", "draconicevolution"]
        self.mod_names = {"geckolib": "GeckoLib", "create": "Create"}

    def test_exact_match(self):
        self.assertEqual(mca_normalize_modid("geckolib", self.mods_keys, self.mod_names), "geckolib")

    def test_case_insensitive_match(self):
        self.assertEqual(mca_normalize_modid("GECKOLIB", self.mods_keys, self.mod_names), "geckolib")

    def test_no_match(self):
        self.assertIsNone(mca_normalize_modid("nonexistent", self.mods_keys, self.mod_names))


# =============================================================================
# 检测器注册表测试
# =============================================================================

class MockDetector(Detector):
    """模拟检测器。"""
    def __init__(self, name="MockDetector", cause_label="MockCause", should_detect=True):
        self._name = name
        self._cause_label = cause_label
        self._should_detect = should_detect
        self.detect_called = False

    def detect(self, crash_log: str, context: AnalysisContext):
        self.detect_called = True
        if self._should_detect:
            context.add_result(f"Detected by {self._name}", self._name, self._cause_label)
        return context.results

    def get_name(self) -> str:
        return self._name

    def get_cause_label(self):
        return self._cause_label


class TestDetectorRegistry(unittest.TestCase):
    """检测器注册表测试。"""

    def setUp(self):
        DetectorRegistry._builtin_class_cache = set()
        DetectorRegistry._inited = False

    def test_empty_registry(self):
        registry = DetectorRegistry()
        self.assertEqual(registry.list(), [])

    def test_register_detector(self):
        registry = DetectorRegistry()
        detector = MockDetector()
        registry.register(detector)
        self.assertEqual(len(registry.list()), 1)

    def test_run_all_with_mock_analyzer(self):
        registry = DetectorRegistry()
        detector = MockDetector()
        registry.register(detector)
        analyzer = MagicMock()
        analyzer.crash_log = "Test crash log"
        results = registry.run_all(analyzer)
        self.assertTrue(detector.detect_called)
        self.assertEqual(len(results), 1)

    def test_load_builtins(self):
        registry = DetectorRegistry()
        registry.load_builtins()
        self.assertGreater(len(registry.list()), 0)


# =============================================================================
# 运行测试
# =============================================================================

if __name__ == '__main__':
    unittest.main(verbosity=2)
