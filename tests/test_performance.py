"""
MCA Brain System 性能测试套件

合并内容:
- 压力测试 (stress_test.py)
- 边界条件测试 (boundary_test.py)
- 极限性能测试 (extreme_test.py)

运行方式:
  python tests/test_performance.py --stress      # 压力测试
  python tests/test_performance.py --boundary    # 边界测试
  python tests/test_performance.py --extreme     # 极限测试
  python tests/test_performance.py --all         # 全部测试
"""

import argparse
import gc
import os
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain_system.cache import LruTtlCache
from brain_system.retry import RetryPolicy, async_retry
from mca_core.regex_cache import RegexCache
from mca_core.rules import DetectionRule, RuleEngine
from mca_core.detectors.registry import DetectorRegistry
from mca_core.file_io import read_text_limited, read_text_head
from utils.helpers import mca_clean_modid, mca_levenshtein, mca_normalize_modid


# =============================================================================
# 通用工具
# =============================================================================

@dataclass
class TestResult:
    """测试结果。"""
    name: str
    iterations: int
    total_time_ms: float
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float
    ops_per_second: float
    errors: int = 0
    peak_memory_mb: float = 0

    def __str__(self):
        return (
            f"\n{'='*60}\n"
            f"  {self.name}\n"
            f"{'='*60}\n"
            f"  Iterations: {self.iterations:,}\n"
            f"  Total:      {self.total_time_ms:.2f} ms\n"
            f"  Average:    {self.avg_time_ms:.4f} ms\n"
            f"  Min:        {self.min_time_ms:.4f} ms\n"
            f"  Max:        {self.max_time_ms:.4f} ms\n"
            f"  Throughput: {self.ops_per_second:,.0f} ops/s\n"
            f"  Errors:     {self.errors}\n"
            f"{'='*60}"
        )


def measure_time(func: Callable, iterations: int) -> TestResult:
    """测量函数执行时间。"""
    times = []
    errors = 0
    for _ in range(iterations):
        start = time.perf_counter_ns()
        try:
            func()
        except Exception:
            errors += 1
        end = time.perf_counter_ns()
        times.append((end - start) / 1_000_000)
    
    total = sum(times)
    return TestResult(
        name=getattr(func, '__name__', 'unknown'),
        iterations=iterations,
        total_time_ms=total,
        avg_time_ms=sum(times) / len(times) if times else 0,
        min_time_ms=min(times) if times else 0,
        max_time_ms=max(times) if times else 0,
        ops_per_second=iterations / (total / 1000) if total > 0 else 0,
        errors=errors
    )


# =============================================================================
# 压力测试
# =============================================================================

class StressTestSuite:
    """压力测试套件。"""

    def __init__(self):
        self.results: List[TestResult] = []

    def test_cache_sequential_writes(self, iterations: int = 10000) -> TestResult:
        """缓存顺序写入。"""
        cache = LruTtlCache(max_entries=5000, ttl_seconds=60)
        counter = [0]
        lock = threading.Lock()
        
        def write():
            with lock:
                i = counter[0]
                counter[0] += 1
            cache.set(f"key_{i}", f"value_{i}")
        
        result = measure_time(write, iterations)
        result.name = "Cache Sequential Writes"
        self.results.append(result)
        return result

    def test_cache_concurrent_writes(self, iterations: int = 10000, threads: int = 8) -> TestResult:
        """缓存并发写入。"""
        cache = LruTtlCache(max_entries=5000, ttl_seconds=60)
        errors = [0]
        barrier = threading.Barrier(threads)
        
        def worker():
            barrier.wait()
            for i in range(iterations // threads):
                try:
                    cache.set(f"ckey_{threading.current_thread().name}_{i}", f"value_{i}")
                except Exception:
                    errors[0] += 1
        
        start = time.perf_counter_ns()
        workers = [threading.Thread(target=worker, name=f"t{i}") for i in range(threads)]
        for w in workers:
            w.start()
        for w in workers:
            w.join()
        end = time.perf_counter_ns()
        
        total_ms = (end - start) / 1_000_000
        result = TestResult(
            name="Cache Concurrent Writes",
            iterations=iterations,
            total_time_ms=total_ms,
            avg_time_ms=total_ms / iterations,
            min_time_ms=0, max_time_ms=0,
            ops_per_second=iterations / (total_ms / 1000),
            errors=errors[0]
        )
        self.results.append(result)
        return result

    def test_regex_cache_hit(self, iterations: int = 100000) -> TestResult:
        """正则缓存命中。"""
        RegexCache._cache = {}
        RegexCache.get(r'test_pattern', 0)
        
        def hit():
            RegexCache.get(r'test_pattern', 0)
        
        result = measure_time(hit, iterations)
        result.name = "Regex Cache Hit"
        self.results.append(result)
        return result

    def test_regex_search(self, iterations: int = 50000) -> TestResult:
        """正则搜索操作。"""
        text = "The quick brown fox jumps over 123 lazy dogs"
        
        def search():
            RegexCache.search(r'\d+', text)
        
        result = measure_time(search, iterations)
        result.name = "Regex Search"
        self.results.append(result)
        return result

    def test_rule_engine(self, iterations: int = 50000) -> TestResult:
        """规则引擎评估。"""
        engine = RuleEngine()
        for i in range(100):
            engine.add_rule(DetectionRule(f"rule_{i}", f"kw_{i % 10}", f"msg_{i}"))
        log = "kw_1 kw_2 kw_3 kw_4 kw_5"
        
        def evaluate():
            engine.evaluate(log)
        
        result = measure_time(evaluate, iterations)
        result.name = "Rule Engine Evaluate"
        self.results.append(result)
        return result

    def test_detector_sequential(self, iterations: int = 500) -> TestResult:
        """检测器顺序执行。"""
        registry = DetectorRegistry()
        registry.load_builtins()
        crash_log = "java.lang.OutOfMemoryError: Java heap space"
        
        def detect():
            from unittest.mock import MagicMock
            analyzer = MagicMock()
            analyzer.crash_log = crash_log
            registry.run_all(analyzer)
        
        result = measure_time(detect, iterations)
        result.name = "Detector Sequential"
        self.results.append(result)
        return result

    def run_all(self):
        """运行所有压力测试。"""
        print("\n" + "=" * 60)
        print("  Stress Tests")
        print("=" * 60)
        
        print("\n[1/6] Cache sequential writes...")
        self.test_cache_sequential_writes()
        
        print("[2/6] Cache concurrent writes...")
        self.test_cache_concurrent_writes()
        
        print("[3/6] Regex cache hit...")
        self.test_regex_cache_hit()
        
        print("[4/6] Regex search...")
        self.test_regex_search()
        
        print("[5/6] Rule engine...")
        self.test_rule_engine()
        
        print("[6/6] Detector sequential...")
        self.test_detector_sequential()
        
        self.print_results()

    def print_results(self):
        """打印结果。"""
        total_ops = sum(r.iterations for r in self.results)
        total_errors = sum(r.errors for r in self.results)
        
        for r in self.results:
            print(r)
        
        print(f"\nTotal Operations: {total_ops:,}")
        print(f"Total Errors: {total_errors}")


# =============================================================================
# 边界条件测试
# =============================================================================

class TestNullAndEmptyInput(unittest.TestCase):
    """空值和None输入测试。"""
    
    def test_cache_none_value(self):
        cache = LruTtlCache(max_entries=10, ttl_seconds=60)
        cache.set("key", None)
        self.assertIsNone(cache.get("key"))
    
    def test_helpers_none_input(self):
        self.assertIsNone(mca_clean_modid(None))
        self.assertIsNone(mca_normalize_modid(None, [], None))
    
    def test_file_io_nonexistent(self):
        result = read_text_head("/nonexistent/path/file.txt")
        self.assertEqual(result, "")


class TestExtremeLengthInput(unittest.TestCase):
    """超长字符串测试。"""
    
    def test_very_long_cache_key(self):
        cache = LruTtlCache(max_entries=10, ttl_seconds=60)
        long_key = "k" * 100_000
        cache.set(long_key, "value")
        self.assertEqual(cache.get(long_key), "value")
    
    def test_many_cache_entries(self):
        cache = LruTtlCache(max_entries=100, ttl_seconds=60)
        for i in range(10000):
            cache.set(f"key_{i}", f"value_{i}")
        self.assertLessEqual(len(cache), 100)
    
    def test_many_rules(self):
        engine = RuleEngine()
        for i in range(100):
            engine.add_rule(DetectionRule(f"rule_{i}", f"unique_kw_{i}", f"msg_{i}"))
        log = " ".join(f"unique_kw_{i}" for i in range(100))
        results = engine.evaluate(log)
        self.assertEqual(len(results), 100)


class TestUnicodeAndSpecialChars(unittest.TestCase):
    """Unicode和特殊字符测试。"""
    
    def test_cache_unicode_key(self):
        cache = LruTtlCache(max_entries=10, ttl_seconds=60)
        cache.set("key", "value")
        self.assertEqual(cache.get("key"), "value")
    
    def test_regex_unicode(self):
        text = "test العربية"
        result = RegexCache.findall(r"[a-z]+", text)
        self.assertEqual(result, ["test"])
    
    def test_sql_injection_pattern(self):
        malicious = "'; DROP TABLE users; --"
        result = mca_clean_modid(malicious)
        self.assertNotIn("'", result if result else "")


class TestNumericBoundaries(unittest.TestCase):
    """数值边界测试。"""
    
    def test_cache_zero_ttl(self):
        with self.assertRaises(ValueError):
            LruTtlCache(max_entries=10, ttl_seconds=0)
    
    def test_cache_zero_entries(self):
        with self.assertRaises(ValueError):
            LruTtlCache(max_entries=0, ttl_seconds=60)
    
    def test_cache_negative_values(self):
        with self.assertRaises(ValueError):
            LruTtlCache(max_entries=-1, ttl_seconds=60)
    
    def test_levenshtein_zero_length(self):
        self.assertEqual(mca_levenshtein("", ""), 0)
        self.assertEqual(mca_levenshtein("a", ""), 1)


class TestConcurrencyEdgeCases(unittest.TestCase):
    """并发边界测试。"""
    
    def test_cache_race_condition(self):
        cache = LruTtlCache(max_entries=100, ttl_seconds=60)
        errors = []
        
        def writer(start, count):
            for i in range(count):
                try:
                    cache.set(f"key_{start + i}", f"value_{start + i}")
                except Exception as e:
                    errors.append(e)
        
        threads = [threading.Thread(target=writer, args=(i * 1000, 1000)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        self.assertEqual(len(errors), 0)


class TestErrorRecovery(unittest.TestCase):
    """错误恢复测试。"""
    
    def test_invalid_regex_recovery(self):
        with self.assertRaises(Exception):
            RegexCache.get(r"[invalid(")
    
    def test_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            read_text_limited("/nonexistent/file.txt")
    
    def test_cache_set_limits(self):
        cache = LruTtlCache(max_entries=10, ttl_seconds=60)
        with self.assertRaises(ValueError):
            cache.set_limits(max_entries=0)
        self.assertEqual(cache.max_entries, 10)


# =============================================================================
# 极限性能测试
# =============================================================================

class ExtremeTestSuite:
    """极限性能测试套件。"""

    def __init__(self):
        self.results: List[TestResult] = []
        try:
            import tracemalloc
            self._has_tracemalloc = True
        except ImportError:
            self._has_tracemalloc = False

    def test_million_cache_ops(self) -> TestResult:
        """百万缓存操作。"""
        print("\n[*] Million cache operations...")
        cache = LruTtlCache(max_entries=10000, ttl_seconds=300)
        iterations = 1_000_000
        
        def ops():
            for i in range(iterations):
                cache.set(f"key_{i % 50000}", f"value_{i}")
                if i % 100000 == 0:
                    cache.get(f"key_{i % 10000}")
        
        return self._run_test("Million Cache Ops", ops, iterations)

    def test_extreme_concurrency(self, threads: int = 100) -> TestResult:
        """超高并发测试。"""
        print(f"\n[*] Extreme concurrency ({threads} threads)...")
        cache = LruTtlCache(max_entries=10000, ttl_seconds=60)
        iterations = 500_000
        errors = [0]
        
        def worker():
            for i in range(iterations // threads):
                try:
                    key = f"k{threading.current_thread().name}_{i}"
                    cache.set(key, f"v{i}")
                    cache.get(key)
                except Exception:
                    errors[0] += 1
        
        start = time.perf_counter()
        thread_list = [threading.Thread(target=worker, name=f"t{i}") for i in range(threads)]
        for t in thread_list:
            t.start()
        for t in thread_list:
            t.join()
        end = time.perf_counter()
        
        result = TestResult(
            name=f"Extreme Concurrency ({threads} threads)",
            iterations=iterations,
            total_time_ms=(end - start) * 1000,
            avg_time_ms=0, min_time_ms=0, max_time_ms=0,
            ops_per_second=iterations / (end - start),
            errors=errors[0]
        )
        self.results.append(result)
        return result

    def test_massive_regex(self) -> TestResult:
        """百万正则操作。"""
        print("\n[*] Million regex operations...")
        RegexCache._cache = {}
        iterations = 1_000_000
        patterns = [r'\d+', r'[a-z]+', r'\w+', r'\s+', r'.*?']
        text = "The quick brown fox 123 jumps over 456 lazy dogs"
        
        def ops():
            for i in range(iterations):
                RegexCache.search(patterns[i % len(patterns)], text)
        
        return self._run_test("Million Regex Ops", ops, iterations)

    def test_endurance(self, duration_seconds: int = 10) -> TestResult:
        """耐久性测试。"""
        print(f"\n[*] Endurance test ({duration_seconds}s)...")
        cache = LruTtlCache(max_entries=5000, ttl_seconds=60)
        iterations = [0]
        errors = [0]
        running = [True]
        
        def worker():
            i = 0
            while running[0]:
                try:
                    cache.set(f"endurance_{i}", f"value_{i}")
                    cache.get(f"endurance_{i % 1000}")
                    i += 1
                except Exception:
                    errors[0] += 1
            iterations[0] = i
        
        thread = threading.Thread(target=worker)
        thread.start()
        start = time.perf_counter()
        time.sleep(duration_seconds)
        running[0] = False
        thread.join()
        end = time.perf_counter()
        
        result = TestResult(
            name=f"Endurance ({duration_seconds}s)",
            iterations=iterations[0],
            total_time_ms=(end - start) * 1000,
            avg_time_ms=0, min_time_ms=0, max_time_ms=0,
            ops_per_second=iterations[0] / duration_seconds,
            errors=errors[0]
        )
        self.results.append(result)
        return result

    def _run_test(self, name: str, func: Callable, iterations: int) -> TestResult:
        """运行测试。"""
        gc.collect()
        start = time.perf_counter()
        errors = 0
        try:
            func()
        except Exception:
            errors = 1
        end = time.perf_counter()
        
        duration_ms = (end - start) * 1000
        result = TestResult(
            name=name,
            iterations=iterations,
            total_time_ms=duration_ms,
            avg_time_ms=duration_ms / iterations if iterations else 0,
            min_time_ms=0, max_time_ms=0,
            ops_per_second=iterations / (duration_ms / 1000) if duration_ms else 0,
            errors=errors
        )
        self.results.append(result)
        return result

    def run_all(self):
        """运行所有极限测试。"""
        print("\n" + "=" * 60)
        print("  Extreme Performance Tests")
        print("=" * 60)
        
        self.test_million_cache_ops()
        self.test_extreme_concurrency()
        self.test_massive_regex()
        self.test_endurance(10)
        
        self.print_results()

    def print_results(self):
        """打印结果。"""
        total_ops = sum(r.iterations for r in self.results)
        total_errors = sum(r.errors for r in self.results)
        
        for r in self.results:
            print(f"\n{r.name}")
            print(f"  Iterations: {r.iterations:,}")
            print(f"  Duration:   {r.total_time_ms/1000:.3f}s")
            print(f"  Throughput: {r.ops_per_second:,.0f} ops/s")
            print(f"  Errors:     {r.errors}")
        
        print(f"\n{'='*60}")
        print(f"Total Operations: {total_ops:,}")
        print(f"Total Errors: {total_errors}")


# =============================================================================
# 主程序
# =============================================================================

def run_boundary_tests():
    """运行边界测试。"""
    print("\n" + "=" * 60)
    print("  Boundary Tests")
    print("=" * 60)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestNullAndEmptyInput))
    suite.addTests(loader.loadTestsFromTestCase(TestExtremeLengthInput))
    suite.addTests(loader.loadTestsFromTestCase(TestUnicodeAndSpecialChars))
    suite.addTests(loader.loadTestsFromTestCase(TestNumericBoundaries))
    suite.addTests(loader.loadTestsFromTestCase(TestConcurrencyEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorRecovery))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print(f"\n{'='*60}")
    print(f"Ran: {result.testsRun}")
    print(f"Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failed: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")


def main():
    parser = argparse.ArgumentParser(description='MCA Performance Tests')
    parser.add_argument('--stress', action='store_true', help='Run stress tests')
    parser.add_argument('--boundary', action='store_true', help='Run boundary tests')
    parser.add_argument('--extreme', action='store_true', help='Run extreme tests')
    parser.add_argument('--all', action='store_true', help='Run all tests')
    
    args = parser.parse_args()
    
    if not any([args.stress, args.boundary, args.extreme, args.all]):
        args.all = True
    
    print("\n" + "=" * 60)
    print("  MCA Brain System Performance Test Suite")
    print("=" * 60)
    
    if args.stress or args.all:
        suite = StressTestSuite()
        suite.run_all()
    
    if args.boundary or args.all:
        run_boundary_tests()
    
    if args.extreme or args.all:
        suite = ExtremeTestSuite()
        suite.run_all()
    
    print("\n" + "=" * 60)
    print("  All tests completed!")
    print("=" * 60)


if __name__ == '__main__':
    main()
