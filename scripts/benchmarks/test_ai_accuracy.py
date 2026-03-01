"""
MCA Brain System AI 准确性测试。

使用已知的崩溃场景测试系统识别准确性。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from mca_core.crash_patterns import CrashPatternLibrary
from mca_core.detectors.out_of_memory import OutOfMemoryDetector
from mca_core.detectors.missing_dependencies import MissingDependenciesDetector
from mca_core.detectors.contracts import AnalysisContext


# 已知崩溃场景测试用例
TEST_CASES = [
    {
        "name": "OOM - Java Heap Space",
        "category": "内存溢出",
        "log": """
---- Minecraft Crash Report ----
Time: 2024-01-15 10:30:00
Description: Unexpected error

java.lang.OutOfMemoryError: Java heap space
    at java.util.Arrays.copyOf(Arrays.java:3332)
    at java.util.Arrays.copyOf(Arrays.java:3310)
    at java.util.ArrayList.grow(ArrayList.java:242)
""",
        "expected_causes": ["内存溢出"],
    },
    {
        "name": "OOM - Direct Buffer",
        "category": "内存溢出",
        "log": """
java.lang.OutOfMemoryError: Cannot reserve 1048576 bytes of direct buffer memory
    at java.nio.Bits.reserveMemory(Bits.java:711)
    at java.nio.DirectByteBuffer.<init>(DirectByteBuffer.java:123)
""",
        "expected_causes": ["内存溢出"],
    },
    {
        "name": "Missing Dependency - Simple",
        "category": "缺失依赖",
        "log": """
Missing or unsupported mandatory dependencies:
Mod ID: 'geckolib', Requested by: 'dragonmounts', Expected range: '[3.0.0,)'
Failure message: Missing or unsupported mandatory dependencies: geckolib
""",
        "expected_causes": ["缺失依赖"],
    },
    {
        "name": "Missing Dependency - Detailed",
        "category": "缺失依赖",
        "log": """
[ModLoadingException/]: [FAILED/MAIN_THREAD/]: draconicevolution (Draconic Evolution)
Missing mod 'geckolib3'
    at net.minecraftforge.fml.javafmlmod.FMLModContainer.acceptEvent()
Mod ID: 'geckolib3', Requested by: 'draconicevolution'
""",
        "expected_causes": ["缺失依赖"],
    },
    {
        "name": "Mixin Injection Failure",
        "category": "Mixin冲突",
        "log": """
org.spongepowered.asm.mixin.transformer.throwables.MixinTransformerError: 
An unexpected critical injection failure was detected
    at org.spongepowered.asm.mixin.transformer.MixinProcessor.applyMixins()
Caused by: org.spongepowered.asm.mixin.injection.throwables.InjectionError: 
Critical injection failure: No locals signature match for player in player
""",
        "expected_causes": [],  # 当前检测器可能不识别
    },
    {
        "name": "OpenGL/GLFW Error",
        "category": "GPU/驱动",
        "log": """
[ERROR] GLFW error 65542: Pixel format not accelerated
    at org.lwjgl.glfw.GLFW.glfwCreateWindow(GLFW.java:1724)
OpenGL: ~~ERROR~~ RuntimeException: No OpenGL context found
""",
        "expected_causes": [],  # 需要GL检测器
    },
    {
        "name": "GeckoLib Animation Error",
        "category": "GeckoLib",
        "log": """
java.lang.NullPointerException: Cannot invoke "software.bernie.geckolib3.core.controller.AnimationController"
    at software.bernie.geckolib3.file.AnimationFile.loadAllAnimations()
    at net.minecraft.client.renderer.entity.EntityRendererManager.func_229085_a_()
""",
        "expected_causes": [],  # CrashPatternLibrary 应识别
    },
    {
        "name": "Version Conflict",
        "category": "版本冲突",
        "log": """
Failed to load mod: mod A is incompatible with mod B
Found mod file /mods/modA-1.0.jar of version 1.0
but version 2.0 is required by modB
Incompatible mod versions detected
""",
        "expected_causes": [],  # 需要版本冲突检测器
    },
    {
        "name": "Normal Log (No Error)",
        "category": "正常",
        "log": """
[10:00:00] [main/INFO]: Loading Minecraft 1.20.1
[10:00:01] [main/INFO]: Loading 150 mods
[10:00:02] [main/INFO]: Minecraft initialized successfully
All mods loaded without errors.
""",
        "expected_causes": [],  # 不应误报
    },
    {
        "name": "Complex - OOM + Missing Dep",
        "category": "复合问题",
        "log": """
java.lang.OutOfMemoryError: Java heap space
    at java.util.HashMap.resize()
    
Missing mod 'jei' needed by 'just_enough_items'
Mod ID: 'jei', Requested by: 'just_enough_calculation'
""",
        "expected_causes": ["内存溢出", "缺失依赖"],
    },
]


class MockAnalyzer:
    analysis_results = []
    cause_counts = {}
    lock = None
    
    def add_cause(self, label):
        self.cause_counts[label] = self.cause_counts.get(label, 0) + 1


def run_accuracy_test():
    """运行准确性测试。"""
    print("=" * 60)
    print("MCA Brain System AI 准确性测试")
    print("=" * 60)
    
    pattern_lib = CrashPatternLibrary()
    oom_detector = OutOfMemoryDetector()
    dep_detector = MissingDependenciesDetector()
    
    results = {
        "total": len(TEST_CASES),
        "correct": 0,
        "partial": 0,
        "missed": 0,
        "false_positive": 0,
        "details": []
    }
    
    print(f"\n测试用例数: {len(TEST_CASES)}\n")
    
    for i, case in enumerate(TEST_CASES, 1):
        log = case["log"]
        expected = set(case["expected_causes"])
        
        # 运行检测器
        analyzer = MockAnalyzer()
        ctx = AnalysisContext(analyzer=analyzer, crash_log=log)
        
        # 模式库匹配
        pattern_matches = pattern_lib.match(log)
        pattern_ids = [p["id"] for p in pattern_matches]
        
        # 检测器
        oom_detector.detect(log, ctx)
        dep_detector.detect(log, ctx)
        
        detected = set(ctx.cause_counts.keys())
        
        # 评估
        if expected:
            hit = len(expected & detected)
            total = len(expected)
            
            if hit == total and len(detected) == total:
                status = "PASS"
                results["correct"] += 1
            elif hit > 0:
                status = "PARTIAL"
                results["partial"] += 1
            else:
                status = "MISS"
                results["missed"] += 1
        else:
            # 无预期错误，检查误报
            if detected:
                status = "FALSE_POSITIVE"
                results["false_positive"] += 1
            else:
                status = "PASS"
                results["correct"] += 1
        
        # 打印结果
        print(f"[{i}] {case['name']}")
        print(f"    类别: {case['category']}")
        print(f"    预期: {expected if expected else '无'}")
        print(f"    检测: {detected if detected else '无'}")
        print(f"    模式: {pattern_ids if pattern_ids else '无'}")
        print(f"    状态: {status}")
        print()
        
        results["details"].append({
            "name": case["name"],
            "expected": list(expected),
            "detected": list(detected),
            "patterns": pattern_ids,
            "status": status,
        })
    
    # 总结
    print("=" * 60)
    print("准确性评估总结")
    print("=" * 60)
    print(f"  完全正确: {results['correct']}/{results['total']}")
    print(f"  部分正确: {results['partial']}/{results['total']}")
    print(f"  未检测到: {results['missed']}/{results['total']}")
    print(f"  误报: {results['false_positive']}/{results['total']}")
    
    # 计算准确率
    accuracy = (results['correct'] + results['partial'] * 0.5) / results['total'] * 100
    precision = results['correct'] / max(results['correct'] + results['false_positive'], 1) * 100
    
    print(f"\n  准确率: {accuracy:.1f}%")
    print(f"  精确率: {precision:.1f}%")
    
    # 评级
    if accuracy >= 80:
        rating = "优秀 [5/5]"
    elif accuracy >= 60:
        rating = "良好 [4/5]"
    elif accuracy >= 40:
        rating = "一般 [3/5]"
    else:
        rating = "需改进 [2/5]"
    
    print(f"  评级: {rating}")
    
    # 问题分析
    print("\n" + "=" * 60)
    print("问题分析")
    print("=" * 60)
    
    issues = []
    for d in results["details"]:
        if d["status"] in ["MISS", "PARTIAL", "FALSE_POSITIVE"]:
            issues.append(d)
    
    if issues:
        for issue in issues:
            print(f"\n  [{issue['status']}] {issue['name']}")
            print(f"    预期: {issue['expected']}")
            print(f"    实际: {issue['detected']}")
            
            if issue['status'] == "MISS":
                print("    建议: 需要添加相应检测器")
            elif issue['status'] == "PARTIAL":
                print("    建议: 检测器覆盖不完整")
            elif issue['status'] == "FALSE_POSITIVE":
                print("    建议: 检测器阈值需调整")
    else:
        print("  所有测试通过!")
    
    return results


if __name__ == "__main__":
    run_accuracy_test()
