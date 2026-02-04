import re

class CrashPatternLibrary:
    def __init__(self):
        self.patterns = [
            {
                "id": "geckolib_animation",
                "name": "GeckoLib 动画错误",
                "keywords": ["software.bernie.geckolib", "AnimationController", "NullPointerException"],
                "advice": "GeckoLib 动画控制器发生空指针异常。通常是由于实体模型或动画文件缺失/损坏导致。尝试更新 GeckoLib 或移除报错实体所属的模组。"
            },
            {
                "id": "mixin_injection",
                "name": "Mixin 注入失败",
                "keywords": ["org.spongepowered.asm.mixin.transformer.MixinProcessor", "InjectionError", "Critical injection failure"],
                "advice": "Mixin 注入失败。这通常意味着两个模组试图修改同一段代码并发生冲突。检查日志中提到的 'Target' 类和 'Handler' 方法，找出冲突的模组。"
            },
            {
                "id": "tessellator_crash",
                "name": "Tessellator 渲染错误",
                "keywords": ["net.minecraft.client.renderer.Tessellator", "BufferBuilder", "Not tessellating"],
                "advice": "Tessellator 状态异常。通常由渲染类模组（如 OptiFine, Sodium, Canvas）引起。尝试禁用这些模组或调整渲染设置。"
            },
            {
                "id": "glfw_error",
                "name": "GLFW 窗口/输入错误",
                "keywords": ["org.lwjgl.glfw.GLFW", "GLFW error", "Pixel format not accelerated"],
                "advice": "GLFW 底层错误。可能是显卡驱动过旧、不支持 OpenGL 版本或被其他软件（如录屏软件、覆盖层）干扰。更新显卡驱动或关闭后台干扰软件。"
            }
        ]

    def match(self, log_content):
        matches = []
        for pattern in self.patterns:
            score = 0
            for kw in pattern["keywords"]:
                if kw in log_content:
                    score += 1
            
            if score >= 2: # Simple heuristic: match at least 2 keywords or 1 very specific one? 
                           # Let's say if 2 keywords match, it's a strong candidate.
                           # Or if the first keyword (package name) is very specific.
                matches.append(pattern)
            elif score == 1 and len(pattern["keywords"]) == 1:
                 matches.append(pattern)
                 
        return matches
