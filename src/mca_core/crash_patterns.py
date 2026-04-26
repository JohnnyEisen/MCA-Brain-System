import re
from typing import List, Dict, Any, Optional

from mca_core.regex_cache import RegexCache


class CrashPatternLibrary:
    def __init__(self):
        self.patterns: List[Dict[str, Any]] = [
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

    def match(self, log_content: Optional[str]) -> List[Dict[str, Any]]:
        if log_content is None:
            return []
        
        matches = []
        log_lower = log_content.lower()
        
        for pattern in self.patterns:
            score = 0
            keywords = pattern["keywords"]
            
            for kw in keywords:
                try:
                    if RegexCache.search(re.escape(kw), log_content, flags=re.IGNORECASE):
                        score += 1
                except re.error:
                    if kw.lower() in log_lower:
                        score += 1
            
            if score >= 2:
                matches.append({
                    "id": pattern["id"],
                    "name": pattern["name"],
                    "advice": pattern["advice"]
                })
            elif score == 1 and len(keywords) == 1:
                matches.append({
                    "id": pattern["id"],
                    "name": pattern["name"],
                    "advice": pattern["advice"]
                })
                
        return matches
