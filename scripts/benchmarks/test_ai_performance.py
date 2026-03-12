"""
MCA Brain System AI 性能测试脚本。

测试项目：
1. BrainCore 初始化时间
2. DLC 加载时间
3. 异步任务执行性能
4. 语义分析性能（如有）
5. 并发任务吞吐量
"""

import sys
import time
import asyncio
import os

# 确保路径正确
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

print(f"Python: {sys.version}")
print(f"Working Dir: {os.getcwd()}")
print("-" * 50)


def test_import_time():
    """测试模块导入时间。"""
    print("\n[1] 模块导入性能测试")
    
    # BrainCore
    t0 = time.perf_counter()
    from brain_system.core import BrainCore
    brain_import = time.perf_counter() - t0
    print(f"  BrainCore 导入: {brain_import*1000:.2f}ms")
    
    # CrashPatternLearner
    t0 = time.perf_counter()
    from mca_core.learning import CrashPatternLearner
    learner_import = time.perf_counter() - t0
    print(f"  CrashPatternLearner 导入: {learner_import*1000:.2f}ms")
    
    # 检测器
    t0 = time.perf_counter()
    from mca_core.detectors import DetectorRegistry
    detector_import = time.perf_counter() - t0
    print(f"  DetectorRegistry 导入: {detector_import*1000:.2f}ms")
    
    return {
        "brain_import_ms": brain_import * 1000,
        "learner_import_ms": learner_import * 1000,
        "detector_import_ms": detector_import * 1000,
    }


def test_brain_init():
    """测试 BrainCore 初始化性能。"""
    print("\n[2] BrainCore 初始化测试")
    
    from brain_system.core import BrainCore
    
    # 无配置初始化
    t0 = time.perf_counter()
    brain = BrainCore(config_path=None)
    init_time = time.perf_counter() - t0
    print(f"  初始化时间: {init_time*1000:.2f}ms")
    
    # 检查线程池
    print(f"  线程池 workers: {brain.thread_pool._max_workers if brain.thread_pool else 'N/A'}")
    print(f"  进程池 workers: {brain.process_pool._max_workers if brain.process_pool else 'N/A'}")
    
    # 清理
    try:
        if hasattr(brain, 'shutdown'):
            if hasattr(brain.shutdown, '__await__'):
                # async shutdown, skip in sync context
                pass
            else:
                brain.shutdown()
    except Exception:
        pass
    
    return {"init_time_ms": init_time * 1000}


async def test_async_compute():
    """测试异步计算性能。"""
    print("\n[3] 异步计算性能测试")
    
    from brain_system.core import BrainCore
    
    brain = BrainCore(config_path=None)
    
    # 使用顶层函数避免进程池序列化问题
    def _cpu_task(n):
        return sum(i * i for i in range(n))
    
    def _io_task():
        time.sleep(0.01)
        return "done"
    
    # 串行基准
    t0 = time.perf_counter()
    for _ in range(5):
        _cpu_task(10000)
    serial_time = time.perf_counter() - t0
    print(f"  串行 5x CPU 任务: {serial_time*1000:.2f}ms")
    
    # 并行测试 (使用线程池，避免进程池序列化问题)
    t0 = time.perf_counter()
    tasks = [brain.compute(f"thread_cpu_{i}", _cpu_task, 10000) for i in range(5)]
    results = await asyncio.gather(*tasks)
    parallel_time = time.perf_counter() - t0
    print(f"  并行 5x CPU 任务: {parallel_time*1000:.2f}ms")
    print(f"  加速比: {serial_time/parallel_time:.2f}x")
    
    # I/O 模拟任务
    t0 = time.perf_counter()
    tasks = [brain.compute(f"io_{i}", _io_task) for i in range(10)]
    results = await asyncio.gather(*tasks)
    io_time = time.perf_counter() - t0
    print(f"  并行 10x I/O 任务: {io_time*1000:.2f}ms (理论串行: 100ms)")
    
    try:
        if hasattr(brain.shutdown, '__await__'):
            await brain.shutdown()
        else:
            brain.shutdown()
    except:
        pass
    
    return {
        "serial_cpu_ms": serial_time * 1000,
        "parallel_cpu_ms": parallel_time * 1000,
        "speedup": serial_time / parallel_time,
        "parallel_io_ms": io_time * 1000,
    }


def test_pattern_matching():
    """测试模式匹配性能。"""
    print("\n[4] 模式匹配性能测试")
    
    from mca_core.crash_patterns import CrashPatternLibrary
    from mca_core.detectors.out_of_memory import OutOfMemoryDetector
    from mca_core.detectors.missing_dependencies import MissingDependenciesDetector
    from mca_core.detectors.contracts import AnalysisContext
    
    # 生成测试日志
    sample_log = """
    java.lang.OutOfMemoryError: Java heap space
    at java.util.Arrays.copyOf(Arrays.java:3332)
    Missing mod 'geckolib' needed by 'dragonmounts'
    org.spongepowered.asm.mixin.transformer.MixinProcessor: InjectionError
    """ * 100  # 扩大测试
    
    # CrashPatternLibrary 测试
    lib = CrashPatternLibrary()
    
    t0 = time.perf_counter()
    for _ in range(100):
        lib.match(sample_log)
    pattern_time = (time.perf_counter() - t0) / 100
    print(f"  CrashPatternLibrary 平均: {pattern_time*1000:.3f}ms")
    
    # 检测器测试
    class MockAnalyzer:
        analysis_results = []
        cause_counts = {}
        lock = None
        def add_cause(self, label): 
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
    print(f"  双检测器平均: {detector_time*1000:.3f}ms")
    
    return {
        "pattern_match_ms": pattern_time * 1000,
        "detector_ms": detector_time * 1000,
    }


def test_semantic_engine():
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
        
        # 测试 CodeBERT 可用性
        from dlcs.brain_dlc_codebert import CodeBertDLC
        print("  CodeBERT DLC: 可用")
        
        # 简单性能测试
        from mca_core.learning import CrashPatternLearner
        
        learner = CrashPatternLearner(os.path.join(os.path.dirname(__file__), "test_patterns.json"))
        
        # 模拟语义编码
        test_texts = [
            "OutOfMemoryError: Java heap space",
            "Missing mod geckolib",
            "Mixin injection failed",
        ] * 10
        
        t0 = time.perf_counter()
        for text in test_texts:
            learner._extract_features(text)
        extract_time = (time.perf_counter() - t0) / len(test_texts)
        print(f"  特征提取平均: {extract_time*1000:.3f}ms")
        
        return {
            "numpy_version": np.__version__,
            "transformers_version": transformers.__version__,
            "feature_extract_ms": extract_time * 1000,
        }
        
    except ImportError as e:
        print(f"  Transformers: 未安装 ({e})")
        return {"semantic": "transformers_not_available"}


def test_memory_usage():
    """测试内存使用。"""
    print("\n[6] 内存使用测试")
    
    try:
        import psutil
        process = psutil.Process()
        
        # 初始内存
        mem_before = process.memory_info().rss / 1024 / 1024
        
        # 加载核心模块
        from brain_system.core import BrainCore
        from mca_core.learning import CrashPatternLearner
        from mca_core.detectors import DetectorRegistry
        
        mem_after_import = process.memory_info().rss / 1024 / 1024
        print(f"  导入后增量: {mem_after_import - mem_before:.1f}MB")
        
        # 初始化 BrainCore
        brain = BrainCore(config_path=None)
        mem_after_brain = process.memory_info().rss / 1024 / 1024
        print(f"  BrainCore 初始化后: {mem_after_brain - mem_before:.1f}MB")
        
        try:
            brain.shutdown()
        except:
            pass
        
        return {
            "import_mem_mb": mem_after_import - mem_before,
            "brain_mem_mb": mem_after_brain - mem_before,
        }
        
    except ImportError:
        print("  psutil 未安装，跳过内存测试")
        return {"memory": "psutil_not_available"}


async def main():
    """运行所有测试。"""
    print("=" * 50)
    print("MCA Brain System AI 性能测试")
    print("=" * 50)
    
    results = {}
    
    # 1. 导入时间
    results["import"] = test_import_time()
    
    # 2. BrainCore 初始化
    results["brain_init"] = test_brain_init()
    
    # 3. 异步计算
    results["async_compute"] = await test_async_compute()
    
    # 4. 模式匹配
    results["pattern"] = test_pattern_matching()
    
    # 5. 语义引擎
    results["semantic"] = test_semantic_engine()
    
    # 6. 内存使用
    results["memory"] = test_memory_usage()
    
    # 总结
    print("\n" + "=" * 50)
    print("性能评估总结")
    print("=" * 50)
    
    score = 0
    max_score = 5
    
    # 导入性能
    if results["import"]["brain_import_ms"] < 100:
        print("  [PASS] 导入性能优秀")
        score += 1
    else:
        print("  [WARN] 导入性能一般")
    
    # 初始化性能
    if results["brain_init"]["init_time_ms"] < 50:
        print("  [PASS] 初始化性能优秀")
        score += 1
    else:
        print("  [WARN] 初始化性能一般")
    
    # 并行加速
    if results["async_compute"]["speedup"] > 1.5:
        print(f"  [PASS] 并行加速有效 ({results['async_compute']['speedup']:.2f}x)")
        score += 1
    else:
        print(f"  [WARN] 并行加速有限 ({results['async_compute']['speedup']:.2f}x)")
    
    # 模式匹配
    if results["pattern"]["pattern_match_ms"] < 1:
        print("  [PASS] 模式匹配性能优秀")
        score += 1
    else:
        print("  [WARN] 模式匹配性能一般")
    
    # 语义引擎
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
    
    print(f"\n  总分: {score}/{max_score}")
    
    if score >= 4:
        print("  评级: 优秀 [5/5]")
    elif score >= 3:
        print("  评级: 良好 [4/5]")
    elif score >= 2:
        print("  评级: 一般 [3/5]")
    else:
        print("  评级: 需优化 [2/5]")
    
    return results


if __name__ == "__main__":
    asyncio.run(main())
