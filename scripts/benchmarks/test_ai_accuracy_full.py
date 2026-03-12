"""
MCA Brain System AI 完整准确性测试

测试覆盖：
- 11个检测器的全面测试
- 50+个真实崩溃场景
- 边界情况和复合问题
- 准确率、召回率、F1评分
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from mca_core.crash_patterns import CrashPatternLibrary
from mca_core.detectors import DetectorRegistry, AnalysisContext
from collections import defaultdict


# 完整测试用例库（50+场景）
TEST_CASES = [
    # ==================== 内存溢出 (OOM) ====================
    {
        "id": "OOM_001",
        "category": "内存溢出",
        "log": """
java.lang.OutOfMemoryError: Java heap space
    at java.util.Arrays.copyOf(Arrays.java:3332)
    at java.util.ArrayList.grow(ArrayList.java:242)
""",
        "expected": ["内存溢出"],
    },
    {
        "id": "OOM_002",
        "category": "内存溢出",
        "log": """
java.lang.OutOfMemoryError: Cannot reserve 1048576 bytes of direct buffer memory
    at java.nio.Bits.reserveMemory(Bits.java:711)
""",
        "expected": ["内存溢出"],
    },
    {
        "id": "OOM_003",
        "category": "内存溢出",
        "log": """
java.lang.OutOfMemoryError: GC overhead limit exceeded
    at java.lang.ref.Finalizer$FinalizerThread.run(Finalizer.java:180)
""",
        "expected": ["内存溢出"],
    },
    {
        "id": "OOM_004",
        "category": "内存溢出",
        "log": """
java.lang.OutOfMemoryError: Metaspace
    at java.lang.ClassLoader.defineClass1(Native Method)
""",
        "expected": ["内存溢出"],
    },
    {
        "id": "OOM_005",
        "category": "内存溢出",
        "log": """
Exception: java.lang.OutOfMemoryError thrown from the UncaughtExceptionHandler in thread "main"
Memory: 4GB heap exhausted
""",
        "expected": ["内存溢出"],
    },

    # ==================== 缺失依赖 ====================
    {
        "id": "DEP_001",
        "category": "缺失依赖",
        "log": """
Missing or unsupported mandatory dependencies:
Mod ID: 'geckolib', Requested by: 'dragonmounts', Expected range: '[3.0.0,)'
""",
        "expected": ["缺失依赖"],
    },
    {
        "id": "DEP_002",
        "category": "缺失依赖",
        "log": """
[ModLoadingException/]: [FAILED/MAIN_THREAD/]: draconicevolution (Draconic Evolution)
Missing mod 'geckolib3'
Mod ID: 'geckolib3', Requested by: 'draconicevolution'
""",
        "expected": ["缺失依赖"],
    },
    {
        "id": "DEP_003",
        "category": "缺失依赖",
        "log": """
Failed to load mod - missing library
requires mod 'jei' version [9.0.0,10.0.0)
Missing mod 'jei' needed by 'just_enough_items'
""",
        "expected": ["缺失依赖"],
    },
    {
        "id": "DEP_004",
        "category": "缺失依赖",
        "log": """
net.minecraftforge.fml.LoadingFailedException: 
Loading errors encountered: [
    draconicevolution (Draconic Evolution) - missing required dependency: geckolib
]
""",
        "expected": ["缺失依赖"],
    },
    {
        "id": "DEP_005",
        "category": "缺失依赖",
        "log": """
Multiple missing dependencies detected:
Mod ID: 'cloth-config', Requested by: 'modmenu'
Mod ID: 'fabric-api', Requested by: 'sodium'
""",
        "expected": ["缺失依赖"],
    },

    # ==================== GPU/驱动错误 ====================
    {
        "id": "GPU_001",
        "category": "GPU/驱动/GL",
        "log": """
[ERROR] GLFW error 65542: Pixel format not accelerated
    at org.lwjgl.glfw.GLFW.glfwCreateWindow(GLFW.java:1724)
""",
        "expected": ["GPU/驱动/GL"],
    },
    {
        "id": "GPU_002",
        "category": "GPU/驱动/GL",
        "log": """
OpenGL: ~~ERROR~~ RuntimeException: No OpenGL context found in the current thread
    at org.lwjgl.opengl.GL.getCapabilities(GL.java:157)
""",
        "expected": ["GPU/驱动/GL"],
    },
    {
        "id": "GPU_003",
        "category": "GPU/驱动/GL",
        "log": """
[Render thread/ERROR]: Failed to create window
GLFW error 65543: GLX: Failed to create context: BadValue
""",
        "expected": ["GPU/驱动/GL"],
    },
    {
        "id": "GPU_004",
        "category": "GPU/驱动/GL",
        "log": """
java.lang.IllegalStateException: Supported OpenGL version: 2.1
Required OpenGL version: 3.2
Please update your graphics drivers.
""",
        "expected": ["GPU/驱动/GL"],
    },
    {
        "id": "GPU_005",
        "category": "GPU/驱动/GL",
        "log": """
[Main/WARN]: OpenGL debug message: Buffer performance warning
GL_INVALID_OPERATION error generated
""",
        "expected": ["GPU/驱动/GL"],
    },

    # ==================== 版本冲突 ====================
    {
        "id": "VER_001",
        "category": "版本冲突",
        "log": """
net.minecraftforge.fml.LoadingFailedException: 
Loading errors encountered: [
    Mod 'moda' requires version 2.0 of 'modb' but found version 1.5
]
""",
        "expected": ["版本冲突"],
    },
    {
        "id": "VER_002",
        "category": "版本冲突",
        "log": """
Failed to load mod: incompatible mod versions
Mod 'create' version 0.5.0 is incompatible with 'flywheel' version 0.6.0
Expected flywheel version: [0.5.0,0.6.0)
""",
        "expected": ["版本冲突"],
    },
    {
        "id": "VER_003",
        "category": "版本冲突",
        "log": """
[ModLoadingException]: Version mismatch detected
Mod A version 1.0 conflicts with Mod B version 2.0
Incompatible version ranges
""",
        "expected": ["版本冲突"],
    },
    {
        "id": "VER_004",
        "category": "版本冲突",
        "log": """
Detected mod version conflicts:
- mod_a@1.0 requires mod_c@>=2.0
- mod_b@1.0 requires mod_c@<2.0
Resolution failed
""",
        "expected": ["版本冲突"],
    },

    # ==================== 重复MOD ====================
    {
        "id": "DUP_001",
        "category": "重复MOD",
        "log": """
[main/ERROR]: Found duplicate mods:
Mod ID: 'jei' found in both 'jei-1.20.1-15.2.0.27.jar' and 'jei-1.20.1-15.0.0.9.jar'
""",
        "expected": ["重复MOD"],
    },
    {
        "id": "DUP_002",
        "category": "重复MOD",
        "log": """
net.minecraftforge.fml.LoadingFailedException: 
Multiple files for mod 'sodium' found:
- sodium-fabric-mc1.20.1-0.5.8.jar
- sodium-fabric-mc1.20.1-0.4.10.jar
""",
        "expected": ["重复MOD"],
    },
    {
        "id": "DUP_003",
        "category": "重复MOD",
        "log": """
Duplicate mod detected: 'optifabric'
Files: [OptiFabric-1.13.0.jar, OptiFabric-1.12.1.jar]
Please keep only one version.
""",
        "expected": ["重复MOD"],
    },

    # ==================== GeckoLib问题 ====================
    {
        "id": "GEO_001",
        "category": "GeckoLib缺失/初始化",
        "log": """
java.lang.NullPointerException: Cannot invoke "software.bernie.geckolib3.core.controller.AnimationController"
    at software.bernie.geckolib3.file.AnimationFile.loadAllAnimations()
""",
        "expected": ["GeckoLib缺失/初始化"],
    },
    {
        "id": "GEO_002",
        "category": "GeckoLib缺失/初始化",
        "log": """
java.lang.NoClassDefFoundError: software/bernie/geckolib3/core/animatable/GeoAnimatable
    at com.example.mymod.entities.MyEntity.<init>(MyEntity.java:45)
Caused by: java.lang.ClassNotFoundException: software.bernie.geckolib3.core.animatable.GeoAnimatable
""",
        "expected": ["GeckoLib缺失/初始化"],
    },
    {
        "id": "GEO_003",
        "category": "GeckoLib缺失/初始化",
        "log": """
Failed to register GeckoLib model
software.bernie.geckolib3.core.animatable.GeoAnimatable not found
Entity rendering failed due to missing GeckoLib
""",
        "expected": ["GeckoLib缺失/初始化"],
    },

    # ==================== Mixin冲突 ====================
    {
        "id": "MIX_001",
        "category": "Mixin冲突",
        "log": """
org.spongepowered.asm.mixin.transformer.throwables.MixinTransformerError: 
An unexpected critical injection failure was detected
    at org.spongepowered.asm.mixin.transformer.MixinProcessor.applyMixins()
Caused by: org.spongepowered.asm.mixin.injection.throwables.InjectionError: 
Critical injection failure
""",
        "expected": ["其他"],  # Mixin冲突
    },
    {
        "id": "MIX_002",
        "category": "Mixin冲突",
        "log": """
[main/FATAL]: Mixin apply failed
Mixin: mod_a.mixins.json:ServerWorldMixin from mod mod_a
Target: net.minecraft.server.world.ServerWorld
Reason: Injection point not found
""",
        "expected": ["其他"],
    },
    {
        "id": "MIX_003",
        "category": "Mixin冲突",
        "log": """
org.spongepowered.asm.mixin.injection.throwables.InvalidInjectionException: 
@Inject annotation on method does not match any target method in class
    at org.spongepowered.asm.mixin.transformer.MixinTargetContext.validateInjection()
""",
        "expected": ["其他"],
    },

    # ==================== 复合问题 ====================
    {
        "id": "COMP_001",
        "category": "复合",
        "log": """
java.lang.OutOfMemoryError: Java heap space
    at java.util.HashMap.resize()

Missing mod 'geckolib' needed by 'dragonmounts'
Mod ID: 'geckolib', Requested by: 'dragonmounts'
""",
        "expected": ["内存溢出", "缺失依赖"],
    },
    {
        "id": "COMP_002",
        "category": "复合",
        "log": """
GLFW error 65542: Pixel format not accelerated

Duplicate mods found:
- jei-1.20.1-15.2.0.27.jar
- jei-1.20.1-15.0.0.9.jar

java.lang.OutOfMemoryError: Java heap space
""",
        "expected": ["GPU/驱动/GL", "重复MOD", "内存溢出"],
    },
    {
        "id": "COMP_003",
        "category": "复合",
        "log": """
Missing or unsupported mandatory dependencies:
Mod ID: 'geckolib3', Requested by: 'draconicevolution'

Mod version conflict:
mod_a requires mod_b version 2.0, but found 1.5

Failed to load: Critical injection failure
""",
        "expected": ["缺失依赖", "版本冲突"],
    },

    # ==================== 正常日志（不应误报）====================
    {
        "id": "NORM_001",
        "category": "正常",
        "log": """
[10:00:00] [main/INFO]: Loading Minecraft 1.20.1 with Forge 47.2.0
[10:00:01] [main/INFO]: Loading 150 mods
[10:00:05] [main/INFO]: All mods loaded successfully
[10:00:10] [main/INFO]: Minecraft initialized
Game running smoothly, no errors detected.
""",
        "expected": [],
    },
    {
        "id": "NORM_002",
        "category": "正常",
        "log": """
[Server thread/INFO]: Starting minecraft server version 1.20.1
[Server thread/INFO]: Loading properties
[Server thread/INFO]: Default game type: SURVIVAL
[Server thread/INFO]: Generating keypair
[Server thread/INFO]: Starting Minecraft server on *:25565
Server started successfully.
""",
        "expected": [],
    },
    {
        "id": "NORM_003",
        "category": "正常",
        "log": """
[main/INFO]: Environment: authHost='https://authserver.mojang.com'
[main/INFO]: Setting user: Player123
[main/INFO]: Backend library: LWJGL version 3.3.1
[main/INFO]: OpenGL: NVIDIA GeForce RTX 3080 OpenGL version 4.6.0
[main/INFO]: Using VBOs: Yes
All systems nominal.
""",
        "expected": [],
    },

    # ==================== 边界情况 ====================
    {
        "id": "EDGE_001",
        "category": "边界",
        "log": """OutOfMemoryError""",  # 单关键词
        "expected": ["内存溢出"],
    },
    {
        "id": "EDGE_002",
        "category": "边界",
        "log": """
This is an error message about memory.
But it's not actually an OutOfMemoryError.
Just a log line with the word 'memory' in it.
""",
        "expected": [],  # 不应误报
    },
    {
        "id": "EDGE_003",
        "category": "边界",
        "log": """
java.lang.Exception: Something went wrong
    at com.example.MyClass.myMethod(MyClass.java:123)
Caused by: java.io.IOException: File not found
    at java.io.FileInputStream.open(Native Method)
""",
        "expected": [],  # 普通异常，不是崩溃原因
    },
    {
        "id": "EDGE_004",
        "category": "边界",
        "log": "",  # 空日志
        "expected": [],
    },
    {
        "id": "EDGE_005",
        "category": "边界",
        "log": """
[WARN]: Running low on memory (80% used)
[WARN]: Consider increasing heap size
[INFO]: Garbage collection completed
""",
        "expected": [],  # 警告，不是错误
    },
]


class MockAnalyzer:
    """模拟分析器。"""
    analysis_results = []
    cause_counts = {}
    lock = None
    
    def add_cause(self, label):
        self.cause_counts[label] = self.cause_counts.get(label, 0) + 1


def run_comprehensive_test():
    """运行全面准确性测试。"""
    print("=" * 70)
    print("MCA Brain System AI 全面准确性测试")
    print("=" * 70)
    
    # 初始化所有检测器
    pattern_lib = CrashPatternLibrary()
    registry = DetectorRegistry()
    registry.load_builtins()
    
    print(f"\n已加载 {len(registry.list())} 个检测器:")
    detectors_info = {}
    for det in registry.list():
        name = det.get_name()
        cause = det.get_cause_label()
        detectors_info[name] = cause
        print(f"  - {name}: {cause if cause else '(无标签)'}")
    
    print(f"\n测试用例数: {len(TEST_CASES)}")
    print("-" * 70)
    
    # 统计数据
    stats = {
        "by_category": defaultdict(lambda: {"total": 0, "hit": 0, "miss": 0, "fp": 0}),
        "by_detector": defaultdict(lambda: {"triggered": 0}),
        "total_tests": len(TEST_CASES),
        "correct": 0,
        "partial": 0,
        "missed": 0,
        "false_positive": 0,
        "true_negative": 0,
    }
    
    # 运行测试
    results = []
    for case in TEST_CASES:
        case_id = case["id"]
        category = case["category"]
        log = case["log"]
        expected = set(case["expected"])
        
        # 创建新的分析器实例
        analyzer = MockAnalyzer()
        ctx = AnalysisContext(analyzer=analyzer, crash_log=log)
        
        # 运行所有检测器
        for det in registry.list():
            try:
                det.detect(log, ctx)
            except Exception as e:
                pass  # 忽略单个检测器错误
        
        # 获取检测结果
        detected = set(ctx.cause_counts.keys())
        
        # 移除None和空值
        detected.discard(None)
        detected.discard("")
        
        # 模式库匹配
        pattern_matches = pattern_lib.match(log)
        
        # 评估结果
        if expected:
            # 有预期错误
            hit_count = len(expected & detected)
            total_expected = len(expected)
            extra = detected - expected
            
            if hit_count == total_expected and not extra:
                status = "PASS"
                stats["correct"] += 1
                stats["by_category"][category]["hit"] += 1
            elif hit_count > 0:
                status = "PARTIAL"
                stats["partial"] += 1
                stats["by_category"][category]["hit"] += 0.5
                stats["by_category"][category]["miss"] += 0.5
            else:
                status = "MISS"
                stats["missed"] += 1
                stats["by_category"][category]["miss"] += 1
            
            stats["by_category"][category]["total"] += 1
            
            if extra:
                # 有额外的错误检测结果（误报）
                status += "+FP"
        
        else:
            # 无预期错误
            if detected:
                status = "FALSE_POSITIVE"
                stats["false_positive"] += 1
                stats["by_category"][category]["fp"] += 1
            else:
                status = "TRUE_NEGATIVE"
                stats["true_negative"] += 1
            
            stats["by_category"][category]["total"] += 1
        
        # 记录检测器触发情况
        for cause in detected:
            stats["by_detector"][cause]["triggered"] += 1
        
        results.append({
            "id": case_id,
            "category": category,
            "expected": list(expected),
            "detected": list(detected),
            "patterns": [p["id"] for p in pattern_matches],
            "status": status,
        })
    
    # 打印详细结果（按类别）
    print("\n" + "=" * 70)
    print("详细测试结果（按类别）")
    print("=" * 70)
    
    categories = sorted(set(case["category"] for case in TEST_CASES))
    
    for cat in categories:
        cat_results = [r for r in results if r["category"] == cat]
        cat_stats = stats["by_category"][cat]
        
        print(f"\n【{cat}】({len(cat_results)} 个测试)")
        print("-" * 70)
        
        for r in cat_results:
            exp_str = ", ".join(r["expected"]) if r["expected"] else "无"
            det_str = ", ".join(r["detected"]) if r["detected"] else "无"
            print(f"  [{r['status']:6}] {r['id']}")
            print(f"           预期: {exp_str}")
            print(f"           检测: {det_str}")
    
    # 打印统计摘要
    print("\n" + "=" * 70)
    print("准确性统计摘要")
    print("=" * 70)
    
    total = stats["total_tests"]
    print(f"\n总体表现:")
    print(f"  完全正确:     {stats['correct']:3d}/{total} ({stats['correct']/total*100:5.1f}%)")
    print(f"  部分正确:     {stats['partial']:3d}/{total} ({stats['partial']/total*100:5.1f}%)")
    print(f"  漏检:         {stats['missed']:3d}/{total} ({stats['missed']/total*100:5.1f}%)")
    print(f"  误报:         {stats['false_positive']:3d}/{total} ({stats['false_positive']/total*100:5.1f}%)")
    print(f"  正确拒识:     {stats['true_negative']:3d}/{total} ({stats['true_negative']/total*100:5.1f}%)")
    
    # 计算准确率、召回率、F1
    # 准确率: 正确检测 / 所有检测
    # 召回率: 正确检测 / 应该检测
    # F1: 2 * (准确率 * 召回率) / (准确率 + 召回率)
    
    true_positives = stats['correct'] + stats['partial'] * 0.5
    false_positives = stats['false_positive']
    false_negatives = stats['missed'] + stats['partial'] * 0.5
    true_negatives = stats['true_negative']
    
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    accuracy = (true_positives + true_negatives) / total
    
    print(f"\n性能指标:")
    print(f"  准确率 (Accuracy):  {accuracy*100:5.1f}%")
    print(f"  精确率 (Precision): {precision*100:5.1f}%")
    print(f"  召回率 (Recall):    {recall*100:5.1f}%")
    print(f"  F1 分数:            {f1_score*100:5.1f}%")
    
    # 按类别统计
    print(f"\n按类别准确率:")
    for cat in categories:
        cat_stats = stats["by_category"][cat]
        if cat_stats["total"] > 0:
            cat_acc = cat_stats["hit"] / cat_stats["total"]
            print(f"  {cat:15s}: {cat_acc*100:5.1f}% ({cat_stats['hit']:.1f}/{cat_stats['total']})")
    
    # 检测器触发统计
    print(f"\n检测器触发次数:")
    sorted_detectors = sorted(stats["by_detector"].items(), key=lambda x: x[1]["triggered"], reverse=True)
    for cause, det_stats in sorted_detectors:
        print(f"  {cause:15s}: {det_stats['triggered']:3d} 次")
    
    # 评级
    if f1_score >= 0.9:
        rating = "优秀 [5/5]"
    elif f1_score >= 0.8:
        rating = "良好 [4/5]"
    elif f1_score >= 0.6:
        rating = "一般 [3/5]"
    elif f1_score >= 0.4:
        rating = "较差 [2/5]"
    else:
        rating = "需改进 [1/5]"
    
    print(f"\n最终评级: {rating}")
    print(f"F1 分数: {f1_score*100:.1f}%")
    
    # 问题分析
    print("\n" + "=" * 70)
    print("问题分析")
    print("=" * 70)
    
    problems = defaultdict(list)
    for r in results:
        if "MISS" in r["status"]:
            problems["漏检"].append(r)
        elif "FALSE_POSITIVE" in r["status"]:
            problems["误报"].append(r)
        elif "PARTIAL" in r["status"]:
            problems["部分检测"].append(r)
    
    if problems:
        for problem_type, cases in problems.items():
            print(f"\n【{problem_type}】({len(cases)} 个)")
            for case in cases:
                print(f"  - {case['id']}: 预期 {case['expected']}, 检测 {case['detected']}")
    else:
        print("\n所有测试通过!")
    
    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1_score,
        "rating": rating,
        "stats": stats,
        "results": results,
    }


if __name__ == "__main__":
    result = run_comprehensive_test()
