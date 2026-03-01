"""
CrashPatternLibrary 单元测试。

测试覆盖：
- 各类崩溃模式匹配
- 边界情况（空日志、部分匹配、无匹配）
- 性能基准
"""

import unittest
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mca_core.crash_patterns import CrashPatternLibrary


class TestCrashPatterns(unittest.TestCase):
    """崩溃模式匹配基础测试。"""
    
    def setUp(self):
        self.lib = CrashPatternLibrary()

    def test_geckolib_match(self):
        """GeckoLib 动画错误应该被正确识别。"""
        log = """
        java.lang.NullPointerException: Cannot invoke "software.bernie.geckolib3.core.controller.AnimationController" 
        at net.minecraft.client.main.Main.main(Main.java:123)
        """
        matches = self.lib.match(log)
        self.assertTrue(any(m['id'] == 'geckolib_animation' for m in matches))

    def test_mixin_match(self):
        """Mixin 注入失败应该被正确识别。"""
        log = """
        org.spongepowered.asm.mixin.transformer.throwables.MixinTransformerError: An unexpected critical injection failure was detected
        at org.spongepowered.asm.mixin.transformer.MixinProcessor.applyMixins(MixinProcessor.java:392)
        Caused by: org.spongepowered.asm.mixin.injection.throwables.InjectionError: Critical injection failure
        """
        matches = self.lib.match(log)
        self.assertTrue(any(m['id'] == 'mixin_injection' for m in matches))

    def test_no_match(self):
        """正常日志不应触发任何模式。"""
        log = "Everything is fine. No crash here."
        matches = self.lib.match(log)
        self.assertEqual(len(matches), 0)

    def test_partial_match_insufficient(self):
        """单个关键词不足以触发特定模式。"""
        log = "java.lang.NullPointerException: generic error"
        matches = self.lib.match(log)
        self.assertFalse(any(m['id'] == 'geckolib_animation' for m in matches))


class TestTessellatorPattern(unittest.TestCase):
    """Tessellator 渲染错误测试。"""
    
    def setUp(self):
        self.lib = CrashPatternLibrary()
    
    def test_tessellator_match(self):
        """Tessellator 状态异常应该被识别。"""
        log = """
        java.lang.IllegalStateException: Not tessellating!
        at net.minecraft.client.renderer.Tessellator.getBuffer(Tessellator.java:85)
        at net.minecraft.client.renderer.BufferBuilder.begin(BufferBuilder.java:123)
        """
        matches = self.lib.match(log)
        self.assertTrue(
            any(m['id'] == 'tessellator_crash' for m in matches),
            f"Expected tessellator_crash match, got: {[m['id'] for m in matches]}"
        )
    
    def test_tessellator_partial(self):
        """仅提到 Tessellator 不应触发。"""
        log = "Using Tessellator for rendering optimization"
        matches = self.lib.match(log)
        self.assertEqual(len(matches), 0)


class TestGLFWPattern(unittest.TestCase):
    """GLFW 窗口/输入错误测试。"""
    
    def setUp(self):
        self.lib = CrashPatternLibrary()
    
    def test_glfw_error(self):
        """GLFW 错误应该被识别。"""
        log = """
        [ERROR] GLFW error 65542: Pixel format not accelerated
        at org.lwjgl.glfw.GLFW.glfwCreateWindow(GLFW.java:1724)
        """
        matches = self.lib.match(log)
        self.assertTrue(
            any(m['id'] == 'glfw_error' for m in matches),
            f"Expected glfw_error match, got: {[m['id'] for m in matches]}"
        )
    
    def test_glfw_partial(self):
        """仅提到 GLFW 不应触发。"""
        log = "Initializing GLFW window system"
        matches = self.lib.match(log)
        self.assertEqual(len(matches), 0)


class TestEdgeCases(unittest.TestCase):
    """边界情况测试。"""
    
    def setUp(self):
        self.lib = CrashPatternLibrary()
    
    def test_empty_log(self):
        """空日志不应触发任何模式。"""
        matches = self.lib.match("")
        self.assertEqual(len(matches), 0)
    
    def test_none_log(self):
        """None 输入应安全处理。"""
        # CrashPatternLibrary 使用 'in' 操作符，None 会抛出 TypeError
        # 这里测试当前行为，如果需要应该修改库来处理
        with self.assertRaises(TypeError):
            self.lib.match(None)
    
    def test_very_long_log(self):
        """超长日志应能正常处理。"""
        # 构造一个包含模式的长日志
        log = "x" * 100000 + "software.bernie.geckolib AnimationController NullPointerException"
        matches = self.lib.match(log)
        self.assertTrue(any(m['id'] == 'geckolib_animation' for m in matches))
    
    def test_unicode_log(self):
        """Unicode 内容应正常处理。"""
        log = """
        错误: 内存溢出
        software.bernie.geckolib AnimationController NullPointerException
        """
        matches = self.lib.match(log)
        # 不应该崩溃
        self.assertIsInstance(matches, list)


class TestPatternAdvice(unittest.TestCase):
    """测试模式建议内容。"""
    
    def setUp(self):
        self.lib = CrashPatternLibrary()
    
    def test_all_patterns_have_advice(self):
        """所有模式都应该有建议。"""
        for pattern in self.lib.patterns:
            self.assertIn('advice', pattern)
            self.assertTrue(len(pattern['advice']) > 10, 
                          f"Pattern {pattern['id']} has too short advice")
    
    def test_all_patterns_have_required_fields(self):
        """所有模式都应该有必需字段。"""
        required = ['id', 'name', 'keywords', 'advice']
        for pattern in self.lib.patterns:
            for field in required:
                self.assertIn(field, pattern, 
                            f"Pattern missing field: {field}")


class TestPerformance(unittest.TestCase):
    """性能基准测试。"""
    
    def setUp(self):
        self.lib = CrashPatternLibrary()
        # 预生成测试日志
        self.sample_log = """
        java.lang.NullPointerException: Cannot invoke "software.bernie.geckolib3.core.controller.AnimationController"
        at org.spongepowered.asm.mixin.transformer.MixinProcessor.applyMixins
        net.minecraft.client.renderer.Tessellator BufferBuilder Not tessellating
        org.lwjgl.glfw.GLFW error Pixel format not accelerated
        """ * 10  # 重复10次模拟较长日志
    
    def test_match_performance(self):
        """匹配操作应在合理时间内完成。"""
        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            self.lib.match(self.sample_log)
        elapsed = time.perf_counter() - start
        
        avg_time_ms = (elapsed / iterations) * 1000
        # 每次匹配应 < 5ms
        self.assertLess(avg_time_ms, 5.0, 
                       f"Average match time {avg_time_ms:.2f}ms exceeds 5ms threshold")
        print(f"\n[Performance] Average match time: {avg_time_ms:.3f}ms")


if __name__ == '__main__':
    unittest.main(verbosity=2)
