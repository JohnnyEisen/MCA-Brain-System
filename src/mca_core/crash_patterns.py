import re
from typing import List, Dict, Any, Pattern


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
        
        # 预编译正则表达式以提高性能
        self._compiled_patterns: List[Dict[str, Any]] = []
        self._compile_patterns()
    
    def _compile_patterns(self):
        """预编译所有模式以提高匹配性能"""
        for pattern in self.patterns:
            compiled = {
                "id": pattern["id"],
                "name": pattern["name"],
                "keywords": pattern["keywords"],
                "advice": pattern["advice"],
                "regexes": []
            }
            
            for kw in pattern["keywords"]:
                # 转义特殊正则字符，保留灵活性
                try:
                    # 尝试编译为正则表达式（支持更复杂的匹配模式）
                    compiled["regexes"].append(re.compile(kw, re.IGNORECASE))
                except re.error:
                    # 如果失败，回退为简单字符串匹配（已转义）
                    compiled["regexes"].append(None)
            
            self._compiled_patterns.append(compiled)

    def match(self, log_content: str) -> List[Dict[str, Any]]:
        matches = []
        
        for compiled in self._compiled_patterns:
            score = 0
            for i, regex in enumerate(compiled["regexes"]):
                if regex is not None:
                    # 使用预编译的正则表达式
                    if regex.search(log_content):
                        score += 1
                else:
                    # 回退到简单字符串匹配
                    if compiled["keywords"][i] in log_content:
                        score += 1
            
            # 匹配逻辑：至少匹配2个关键词，或只有1个关键词且匹配了
            if score >= 2:
                matches.append({
                    "id": compiled["id"],
                    "name": compiled["name"],
                    "advice": compiled["advice"]
                })
            elif score == 1 and len(compiled["keywords"]) == 1:
                matches.append({
                    "id": compiled["id"],
                    "name": compiled["name"],
                    "advice": compiled["advice"]
                })
                
        return matches
