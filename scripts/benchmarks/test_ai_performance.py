"""
MCA Brain System AI 性能测试脚本。

测试项目：
1. BrainCore 初始化时间
2. DLC 加载时间
3. 异步任务执行性能
4. 语义分析性能（如有）
5. 并发任务吞吐量
6. 改造前后吞吐对比（legacy vs optimized）
7. 小核/大核机器自动调优参数推荐
"""

import argparse
import asyncio
import json
import multiprocessing
import os
import sys
import tempfile
import time
from typing import Any, Dict

# 确保路径正确
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

print(f"Python: {sys.version}")
print(f"Working Dir: {os.getcwd()}")
print("-" * 50)


def _bench_cpu_task(n: int) -> int:
    """可被进程池安全序列化的 CPU 任务。"""
    return sum(i * i for i in range(n))


def _bench_io_task(delay_seconds: float = 0.01) -> str:
    """可被线程池执行的 I/O 模拟任务。"""
    time.sleep(delay_seconds)
    return "done"


def _create_temp_config(config: Dict[str, Any]) -> str:
    """写入临时配置文件并返回路径。"""
    fd, path = tempfile.mkstemp(prefix="brain_bench_", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fp:
        json.dump(config, fp, ensure_ascii=False)
    return path


async def _shutdown_brain(brain: Any) -> None:
    """统一关闭 BrainCore，兼容同步/异步 shutdown。"""
    try:
        shutdown = getattr(brain, "shutdown", None)
        if shutdown is None:
            return
        if hasattr(shutdown, "__await__"):
            await shutdown()
        else:
            shutdown()
    except Exception:
        pass


def _safe_speedup(new_value: float, base_value: float) -> float:
    if base_value <= 0:
        return 0.0
    return new_value / base_value


def test_import_time() -> Dict[str, float]:
    """测试模块导入时间。"""
    print("\n[1] 模块导入性能测试")

    t0 = time.perf_counter()
    from brain_system.core import BrainCore

    brain_import = time.perf_counter() - t0
    print(f"  BrainCore 导入: {brain_import * 1000:.2f}ms")

    t0 = time.perf_counter()
    from mca_core.learning import CrashPatternLearner

    learner_import = time.perf_counter() - t0
    print(f"  CrashPatternLearner 导入: {learner_import * 1000:.2f}ms")

    t0 = time.perf_counter()
    from mca_core.detectors import DetectorRegistry

    detector_import = time.perf_counter() - t0
    print(f"  DetectorRegistry 导入: {detector_import * 1000:.2f}ms")

    return {
        "brain_import_ms": brain_import * 1000,
        "learner_import_ms": learner_import * 1000,
        "detector_import_ms": detector_import * 1000,
    }


def test_brain_init() -> Dict[str, float]:
    """测试 BrainCore 初始化性能。"""
    print("\n[2] BrainCore 初始化测试")

    from brain_system.core import BrainCore

    t0 = time.perf_counter()
    brain = BrainCore(config_path=None)
    init_time = time.perf_counter() - t0
    print(f"  初始化时间: {init_time * 1000:.2f}ms")

    print(f"  线程池 workers: {brain.thread_pool._max_workers if brain.thread_pool else 'N/A'}")
    print(f"  进程池 workers: {brain.process_pool._max_workers if brain.process_pool else 'N/A'}")
    print(f"  autotune 档位: {brain.config.get('executor_autotune_resolved_profile', 'manual')}")
    print(f"  路由策略: {brain.config.get('executor_routing_strategy', 'balanced')}")

    try:
        if brain.thread_pool:
            brain.thread_pool.shutdown(wait=True)
        if brain.process_pool:
            brain.process_pool.shutdown(wait=True)
    except Exception:
        pass

    return {"init_time_ms": init_time * 1000}


async def test_async_compute() -> Dict[str, float]:
    """测试异步计算性能。"""
    print("\n[3] 异步计算性能测试")

    from brain_system.core import BrainCore

    cpu_count = max(1, multiprocessing.cpu_count())
    config_path = _create_temp_config(
        {
            "executor_autotune_profile": "manual",
            "executor_routing_strategy": "balanced",
            "thread_pool_size": min(max(cpu_count * 2, 4), 32),
            "process_pool_size": min(cpu_count, 8),
        }
    )

    brain = BrainCore(config_path=config_path)

    try:
        serial_iterations = 80_000
        parallel_tasks = min(max(cpu_count * 2, 8), 32)
        io_tasks = min(max(cpu_count * 4, 16), 64)

        t0 = time.perf_counter()
        for _ in range(parallel_tasks):
            _bench_cpu_task(serial_iterations)
        serial_time = time.perf_counter() - t0
        print(f"  串行 {parallel_tasks}x CPU 任务: {serial_time * 1000:.2f}ms")

        t0 = time.perf_counter()
        tasks = [
            brain.compute(f"cpu_task_async_{i}", _bench_cpu_task, serial_iterations)
            for i in range(parallel_tasks)
        ]
        await asyncio.gather(*tasks)
        parallel_time = time.perf_counter() - t0
        print(f"  并行 {parallel_tasks}x CPU 任务: {parallel_time * 1000:.2f}ms")
        print(f"  加速比: {serial_time / parallel_time:.2f}x")

        t0 = time.perf_counter()
        tasks = [
            brain.compute(f"io_task_async_{i}", _bench_io_task, 0.01)
            for i in range(io_tasks)
        ]
        await asyncio.gather(*tasks)
        io_time = time.perf_counter() - t0
        print(f"  并行 {io_tasks}x I/O 任务: {io_time * 1000:.2f}ms")

        return {
            "serial_cpu_ms": serial_time * 1000,
            "parallel_cpu_ms": parallel_time * 1000,
            "speedup": serial_time / parallel_time,
            "parallel_io_ms": io_time * 1000,
        }
    finally:
        await _shutdown_brain(brain)
        try:
            os.remove(config_path)
        except OSError:
            pass


def test_pattern_matching() -> Dict[str, float]:
    """测试模式匹配性能。"""
    print("\n[4] 模式匹配性能测试")

    from mca_core.crash_patterns import CrashPatternLibrary
    from mca_core.detectors.contracts import AnalysisContext
    from mca_core.detectors.missing_dependencies import MissingDependenciesDetector
    from mca_core.detectors.out_of_memory import OutOfMemoryDetector

    sample_log = """
    java.lang.OutOfMemoryError: Java heap space
    at java.util.Arrays.copyOf(Arrays.java:3332)
    Missing mod 'geckolib' needed by 'dragonmounts'
    org.spongepowered.asm.mixin.transformer.MixinProcessor: InjectionError
    """ * 100

    lib = CrashPatternLibrary()

    t0 = time.perf_counter()
    for _ in range(100):
        lib.match(sample_log)
    pattern_time = (time.perf_counter() - t0) / 100
    print(f"  CrashPatternLibrary 平均: {pattern_time * 1000:.3f}ms")

    class MockAnalyzer:
        analysis_results = []
        cause_counts = {}
        lock = None

        def add_cause(self, label: str) -> None:
            self.cause_counts[label] = self.cause_counts.get(label, 0) + 1

    detector1 = OutOfMemoryDetector()
    detector2 = MissingDependenciesDetector()

    ctx = AnalysisContext(analyzer=MockAnalyzer(), crash_log=sample_log)

    t0 = time.perf_counter()
    for _ in range(100):
        ctx.results = []
        ctx.cause_counts = {}
        detector1.detect(sample_log, ctx)
        detector2.detect(sample_log, ctx)
    detector_time = (time.perf_counter() - t0) / 100
    print(f"  双检测器平均: {detector_time * 1000:.3f}ms")

    return {
        "pattern_match_ms": pattern_time * 1000,
        "detector_ms": detector_time * 1000,
    }


def test_semantic_engine() -> Dict[str, Any]:
    """测试语义引擎性能（如果可用）。"""
    print("\n[5] 语义引擎测试")

    try:
        import numpy as np

        print(f"  NumPy 版本: {np.__version__}")
    except ImportError:
        print("  NumPy: 未安装")
        return {"semantic": "numpy_not_available"}

    try:
        import transformers

        print(f"  Transformers 版本: {transformers.__version__}")

        from dlcs.brain_dlc_codebert import CodeBertDLC

        print("  CodeBERT DLC: 可用")

        from mca_core.learning import CrashPatternLearner

        learner = CrashPatternLearner(os.path.join(os.path.dirname(__file__), "test_patterns.json"))

        test_texts = [
            "OutOfMemoryError: Java heap space",
            "Missing mod geckolib",
            "Mixin injection failed",
        ] * 10

        t0 = time.perf_counter()
        for text in test_texts:
            learner._extract_features(text)
        extract_time = (time.perf_counter() - t0) / len(test_texts)
        print(f"  特征提取平均: {extract_time * 1000:.3f}ms")

        return {
            "numpy_version": np.__version__,
            "transformers_version": transformers.__version__,
            "feature_extract_ms": extract_time * 1000,
        }

    except ImportError as e:
        print(f"  Transformers: 未安装 ({e})")
        return {"semantic": "transformers_not_available"}


def test_memory_usage() -> Dict[str, Any]:
    """测试内存使用。"""
    print("\n[6] 内存使用测试")

    try:
        import psutil

        process = psutil.Process()

        mem_before = process.memory_info().rss / 1024 / 1024

        from brain_system.core import BrainCore
        from mca_core.detectors import DetectorRegistry
        from mca_core.learning import CrashPatternLearner

        mem_after_import = process.memory_info().rss / 1024 / 1024
        print(f"  导入后增量: {mem_after_import - mem_before:.1f}MB")

        brain = BrainCore(config_path=None)
        mem_after_brain = process.memory_info().rss / 1024 / 1024
        print(f"  BrainCore 初始化后: {mem_after_brain - mem_before:.1f}MB")

        try:
            if brain.thread_pool:
                brain.thread_pool.shutdown(wait=True)
            if brain.process_pool:
                brain.process_pool.shutdown(wait=True)
        except Exception:
            pass

        return {
            "import_mem_mb": mem_after_import - mem_before,
            "brain_mem_mb": mem_after_brain - mem_before,
        }

    except ImportError:
        print("  psutil 未安装，跳过内存测试")
        return {"memory": "psutil_not_available"}


def _build_profile_overrides(profile: str, cpu_count: int) -> Dict[str, Any]:
    """构建吞吐测试配置。"""
    common = {
        "enable_disk_cache": False,
        "cache_max_entries": 1,
        "retry_max_attempts": 1,
        "enable_metrics": False,
        "enable_tracing": False,
    }

    if profile == "legacy":
        legacy = {
            "executor_autotune_profile": "manual",
            "executor_routing_strategy": "legacy",
            "thread_pool_size": min(cpu_count * 4, 32),
            "process_pool_size": min(cpu_count, 8),
            "process_pool_payload_max_bytes": 262_144,
        }
        legacy.update(common)
        return legacy

    optimized = {
        "executor_autotune_profile": "auto",
        "thread_pool_size_small_core": min(max(cpu_count * 2, 4), 16),
        "process_pool_size_small_core": max(0, min(cpu_count // 2, 4)),
        "executor_routing_strategy_small_core": "latency",
        "process_pool_payload_max_bytes_small_core": 131_072,
        "thread_pool_size_large_core": min(cpu_count * 4, 64),
        "process_pool_size_large_core": min(cpu_count, 16),
        "executor_routing_strategy_large_core": "throughput",
        "process_pool_payload_max_bytes_large_core": 524_288,
    }
    optimized.update(common)
    return optimized


async def _run_profile_throughput(
    label: str,
    config_overrides: Dict[str, Any],
    *,
    cpu_tasks: int,
    io_tasks: int,
    cpu_iterations: int,
    io_delay_seconds: float,
) -> Dict[str, Any]:
    """运行单个 profile 的 CPU/I/O 吞吐测试。"""
    from brain_system.core import BrainCore

    config_path = _create_temp_config(config_overrides)
    brain = BrainCore(config_path=config_path)

    base_thread = int(brain.performance_stats.get("thread_dispatched_tasks", 0))
    base_process = int(brain.performance_stats.get("process_dispatched_tasks", 0))

    try:
        warmup = [
            brain.compute(f"warm_cpu_{i}", _bench_cpu_task, max(10_000, cpu_iterations // 8))
            for i in range(min(4, cpu_tasks))
        ]
        await asyncio.gather(*warmup)

        t0 = time.perf_counter()
        cpu_jobs = [
            brain.compute(f"cpu_task_bench_{i}", _bench_cpu_task, cpu_iterations)
            for i in range(cpu_tasks)
        ]
        await asyncio.gather(*cpu_jobs)
        cpu_seconds = time.perf_counter() - t0

        t0 = time.perf_counter()
        io_jobs = [
            brain.compute(f"io_task_bench_{i}", _bench_io_task, io_delay_seconds)
            for i in range(io_tasks)
        ]
        await asyncio.gather(*io_jobs)
        io_seconds = time.perf_counter() - t0

        thread_delta = int(brain.performance_stats.get("thread_dispatched_tasks", 0)) - base_thread
        process_delta = int(brain.performance_stats.get("process_dispatched_tasks", 0)) - base_process

        return {
            "profile": label,
            "resolved_profile": brain.config.get("executor_autotune_resolved_profile", "manual"),
            "routing_strategy": brain.config.get("executor_routing_strategy", "balanced"),
            "thread_pool_size": brain.thread_pool._max_workers if brain.thread_pool else 0,
            "process_pool_size": brain.process_pool._max_workers if brain.process_pool else 0,
            "cpu_tasks": cpu_tasks,
            "cpu_seconds": cpu_seconds,
            "cpu_throughput": cpu_tasks / cpu_seconds if cpu_seconds > 0 else 0.0,
            "io_tasks": io_tasks,
            "io_seconds": io_seconds,
            "io_throughput": io_tasks / io_seconds if io_seconds > 0 else 0.0,
            "thread_dispatched_tasks": thread_delta,
            "process_dispatched_tasks": process_delta,
        }
    finally:
        await _shutdown_brain(brain)
        try:
            os.remove(config_path)
        except OSError:
            pass


def _print_profile_result(result: Dict[str, Any]) -> None:
    print(f"  - {result['profile']} (resolved={result['resolved_profile']}, strategy={result['routing_strategy']})")
    print(
        f"    pool(thread/process): {result['thread_pool_size']}/{result['process_pool_size']}, "
        f"dispatch(thread/process): {result['thread_dispatched_tasks']}/{result['process_dispatched_tasks']}"
    )
    print(
        f"    CPU 吞吐: {result['cpu_throughput']:.2f} tasks/s ({result['cpu_seconds'] * 1000:.1f}ms), "
        f"I/O 吞吐: {result['io_throughput']:.2f} tasks/s ({result['io_seconds'] * 1000:.1f}ms)"
    )


def _build_recommendations(cpu_count: int, cpu_speedup: float, io_speedup: float) -> Dict[str, Dict[str, Any]]:
    """基于机器规模和实测结果输出推荐参数。"""
    small_strategy = "latency" if io_speedup >= 1.0 else "balanced"
    large_strategy = "throughput" if cpu_speedup >= 1.0 else "balanced"

    return {
        "small_core": {
            "executor_autotune_profile": "small_core",
            "thread_pool_size": min(max(cpu_count * 2, 4), 16),
            "process_pool_size": max(0, min(cpu_count // 2, 4)),
            "executor_routing_strategy": small_strategy,
            "process_pool_payload_max_bytes": 131_072,
        },
        "large_core": {
            "executor_autotune_profile": "large_core",
            "thread_pool_size": min(cpu_count * 4, 64),
            "process_pool_size": min(cpu_count, 16),
            "executor_routing_strategy": large_strategy,
            "process_pool_payload_max_bytes": 524_288,
        },
    }


async def test_executor_throughput_comparison() -> Dict[str, Any]:
    """测试改造前后吞吐，并给出推荐参数。"""
    print("\n[7] 执行器吞吐对比（before legacy vs after optimized）")

    cpu_count = max(1, multiprocessing.cpu_count())
    cpu_tasks = min(max(cpu_count * 4, 24), 128)
    io_tasks = min(max(cpu_count * 8, 48), 256)
    cpu_iterations = 100_000 if cpu_count <= 8 else 160_000
    io_delay_seconds = 0.01

    print(
        f"  机器核数: {cpu_count}, 负载: cpu_tasks={cpu_tasks}, "
        f"io_tasks={io_tasks}, cpu_iterations={cpu_iterations}"
    )

    baseline = await _run_profile_throughput(
        "before_legacy",
        _build_profile_overrides("legacy", cpu_count),
        cpu_tasks=cpu_tasks,
        io_tasks=io_tasks,
        cpu_iterations=cpu_iterations,
        io_delay_seconds=io_delay_seconds,
    )

    optimized = await _run_profile_throughput(
        "after_optimized",
        _build_profile_overrides("optimized", cpu_count),
        cpu_tasks=cpu_tasks,
        io_tasks=io_tasks,
        cpu_iterations=cpu_iterations,
        io_delay_seconds=io_delay_seconds,
    )

    print("  吞吐结果:")
    _print_profile_result(baseline)
    _print_profile_result(optimized)

    cpu_speedup = _safe_speedup(optimized["cpu_throughput"], baseline["cpu_throughput"])
    io_speedup = _safe_speedup(optimized["io_throughput"], baseline["io_throughput"])

    print(f"  CPU 吞吐提升: {cpu_speedup:.2f}x")
    print(f"  I/O 吞吐提升: {io_speedup:.2f}x")

    recommendations = _build_recommendations(cpu_count, cpu_speedup, io_speedup)
    print("\n  推荐参数（开箱即用）:")
    print(json.dumps(recommendations, indent=2, ensure_ascii=False))

    return {
        "baseline": baseline,
        "optimized": optimized,
        "cpu_speedup": cpu_speedup,
        "io_speedup": io_speedup,
        "recommendations": recommendations,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MCA Brain System AI 性能基准")
    parser.add_argument(
        "--compare-only",
        action="store_true",
        help="仅运行改造前后吞吐对比与参数推荐",
    )
    return parser.parse_args()


async def main() -> Dict[str, Any]:
    """运行所有测试。"""
    args = _parse_args()

    print("=" * 50)
    print("MCA Brain System AI 性能测试")
    print("=" * 50)

    results: Dict[str, Any] = {}

    if not args.compare_only:
        results["import"] = test_import_time()
        results["brain_init"] = test_brain_init()
        results["async_compute"] = await test_async_compute()
        results["pattern"] = test_pattern_matching()
        results["semantic"] = test_semantic_engine()
        results["memory"] = test_memory_usage()

    results["throughput_compare"] = await test_executor_throughput_comparison()

    if args.compare_only:
        return results

    print("\n" + "=" * 50)
    print("性能评估总结")
    print("=" * 50)

    score = 0.0
    max_score = 6.0

    if results["import"]["brain_import_ms"] < 100:
        print("  [PASS] 导入性能优秀")
        score += 1
    else:
        print("  [WARN] 导入性能一般")

    if results["brain_init"]["init_time_ms"] < 80:
        print("  [PASS] 初始化性能优秀")
        score += 1
    else:
        print("  [WARN] 初始化性能一般")

    if results["async_compute"]["speedup"] > 1.2:
        print(f"  [PASS] 并行加速有效 ({results['async_compute']['speedup']:.2f}x)")
        score += 1
    else:
        print(f"  [WARN] 并行加速有限 ({results['async_compute']['speedup']:.2f}x)")

    if results["pattern"]["pattern_match_ms"] < 1:
        print("  [PASS] 模式匹配性能优秀")
        score += 1
    else:
        print("  [WARN] 模式匹配性能一般")

    if isinstance(results["semantic"].get("feature_extract_ms"), float):
        if results["semantic"]["feature_extract_ms"] < 1:
            print("  [PASS] 特征提取性能优秀")
            score += 1
        else:
            print("  [WARN] 特征提取性能一般")
            score += 0.5
    else:
        print("  [SKIP] 语义引擎未完全配置")
        score += 0.5

    compare = results["throughput_compare"]
    if compare["cpu_speedup"] >= 1.0 and compare["io_speedup"] >= 1.0:
        print(
            f"  [PASS] 新调度吞吐不低于 legacy (CPU {compare['cpu_speedup']:.2f}x, I/O {compare['io_speedup']:.2f}x)"
        )
        score += 1
    else:
        print(
            f"  [WARN] 新调度吞吐需进一步调优 (CPU {compare['cpu_speedup']:.2f}x, I/O {compare['io_speedup']:.2f}x)"
        )

    print(f"\n  总分: {score}/{max_score}")

    if score >= 5:
        print("  评级: 优秀 [5/5]")
    elif score >= 4:
        print("  评级: 良好 [4/5]")
    elif score >= 3:
        print("  评级: 一般 [3/5]")
    else:
        print("  评级: 需优化 [2/5]")

    return results


if __name__ == "__main__":
    asyncio.run(main())
