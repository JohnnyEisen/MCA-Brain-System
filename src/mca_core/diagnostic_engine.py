import json
import os
import re
import logging
import hashlib
from collections import OrderedDict
from datetime import datetime
from typing import Any
from mca_core.pattern_repository import get_repository, PatternRepository
from mca_core.regex_cache import RegexCache

logger = logging.getLogger(__name__)

class DiagnosticEngine:
    def __init__(self, data_dir: str, repo: PatternRepository | None = None) -> None:
        self.data_dir = data_dir
        if repo:
            self.repo = repo
        else:
            rules_path = os.path.join(data_dir, "diagnostic_rules.json")
            self.repo = get_repository("json", rules_path)
            
        self.learning_data_file = os.path.join(data_dir, "learning_data.json")
        self.learning_data = self._load_learning_data()
        self.rules = self._load_rules_safely()
        
        self._result_cache: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
        self._cache_max_size = 100

    def _compute_log_hash(self, crash_log: str) -> str:
        """计算日志内容的哈希值用于缓存键。"""
        return hashlib.sha256(crash_log.encode('utf-8')).hexdigest()[:16]

    def _load_rules_safely(self):
        patterns = self.repo.load_all_patterns()
        if not patterns:
            defaults = self._create_default_rules()
            for p in defaults["patterns"]:
                self.repo.save_pattern(p)
            return defaults
        return {"patterns": patterns}

    def _create_default_rules(self):
        default_rules = {
            "patterns": [
                {
                    "id": "startup_crash",
                    "name": "启动崩溃",
                    "regex": ["Initialization failed", "Unable to launch", "Exception in thread \"main\""],
                    "diagnosis": "游戏启动失败，通常是核心库缺失或版本不匹配。",
                    "solutions": ["检查Java版本是否符合游戏要求", "验证游戏核心文件完整性"]
                },
                {
                    "id": "rendering_crash",
                    "name": "渲染崩溃",
                    "regex": ["Tessellating block model", "Rendering entity", "OpenGL Error", "Exit code -1073741819",
                              "OpenGL debug message.*ERROR", "GLFW error", "OpenGL error \\d+",
                              "Unable to initialize OpenGL", "render.*failed", "Chunk rendering failed"],
                    "diagnosis": "渲染过程中发生错误，可能是显卡驱动或光影模组冲突。",
                    "solutions": ["更新显卡驱动", "移除光影包", "检查OptiFine/Sodium等优化模组版本"]
                },
                {
                    "id": "world_loading_crash",
                    "name": "世界加载崩溃",
                    "regex": ["Exception loading blockstate", "Exception ticking world", "Error reading world"],
                    "diagnosis": "加载世界时发生错误，可能是区块损坏或模组实体数据异常。",
                    "solutions": ["尝试使用NBTExplorer修复区块", "移除最近添加的维度/生物模组"]
                },
                {
                    "id": "entity_update_crash",
                    "name": "实体更新崩溃",
                    "regex": ["Ticking entity", "Entity being ticked"],
                    "diagnosis": "实体更新逻辑错误，通常由特定生物或物品引起。",
                    "solutions": ["使用命令/kill @e[type=...]清除报错实体", "移除相关模组"]
                },
                {
                    "id": "out_of_memory",
                    "name": "内存溢出",
                    "regex": ["OutOfMemoryError", "Java heap space", "GC overhead limit exceeded", 
                              "Metaspace", "out of memory", "内存不足"],
                    "diagnosis": "Java 内存不足，可能是分配内存过小或存在内存泄漏。",
                    "solutions": ["增加 JVM 内存分配 (-Xmx 参数)", "检查是否有内存泄漏模组", "减少模组数量"]
                },
                {
                    "id": "missing_dependency",
                    "name": "依赖缺失",
                    "regex": ["Missing.*dependency", "Missing mod", "requires.*not found", 
                              "Could not look up mod dependency", "Requirements.*not met",
                              "Mod resolution failed", "Failed to validate mod dependencies"],
                    "diagnosis": "模组缺少必要的前置模组或依赖库。",
                    "solutions": ["安装缺失的前置模组", "检查模组版本兼容性", "查看模组说明获取依赖列表"]
                },
                {
                    "id": "mixin_conflict",
                    "name": "Mixin 冲突",
                    "regex": ["Mixin apply failed", "Invalid Mixin configuration", "Mixin transformation",
                              "incompatible mixin", "Mixin.*error", "Critical injection failure",
                              "Compatibility error in Mixin"],
                    "diagnosis": "Mixin 注入冲突，多个模组修改了同一游戏代码。",
                    "solutions": ["检查冲突的模组组合", "更新或降级冲突模组", "使用 Rubidium/Sodium 替代 OptiFine"]
                },
                {
                    "id": "version_conflict",
                    "name": "版本冲突",
                    "regex": ["Version mismatch", "incompatible with.*version", "Duplicate mod",
                              "Mod.*failed to load correctly", "requires minecraft.*\\+",
                              "Mod incompatible with game version"],
                    "diagnosis": "模组版本与游戏版本或其他模组不兼容。",
                    "solutions": ["检查模组支持的 Minecraft 版本", "更新模组到兼容版本", "移除重复安装的模组"]
                },
                {
                    "id": "gl_error",
                    "name": "OpenGL 错误",
                    "regex": ["GLFW error", "OpenGL error", "GL_INVALID", "driver does not.*support OpenGL",
                              "buffer state", "render.*failed", "Tesselating.*failed"],
                    "diagnosis": "OpenGL 图形接口错误，通常是显卡驱动问题。",
                    "solutions": ["更新显卡驱动到最新版本", "降低图形设置", "禁用 VBO 或光影"]
                },
                {
                    "id": "compound_error",
                    "name": "复合错误",
                    "regex": ["Multiple errors detected", "Compound failure", "Cascading error"],
                    "diagnosis": "多个错误同时发生，需要逐个排查。",
                    "solutions": ["查看完整日志定位首要错误", "按优先级修复各个问题"]
                }
            ]
        }
        return default_rules

    def _load_learning_data(self) -> dict[str, list[dict[str, str]]]:
        if not os.path.exists(self.learning_data_file):
            return {"user_solutions": []}
        try:
            with open(self.learning_data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {"user_solutions": []}

    def analyze(self, crash_log: str) -> list[dict[str, str | list[str]]]:
        """分析崩溃日志，返回匹配的诊断结果。
        
        优化：使用结果缓存避免重复分析相同日志。
        """
        log_hash = self._compute_log_hash(crash_log)
        
        if log_hash in self._result_cache:
            self._result_cache.move_to_end(log_hash)
            return self._result_cache[log_hash]
        
        results: list[dict[str, str | list[str]]] = []
        
        for pattern in self.rules.get("patterns", []):
            matched = False
            for regex in pattern.get("regex", []):
                if RegexCache.search(regex, crash_log, flags=re.IGNORECASE):
                    matched = True
                    break
            
            if matched:
                results.append({
                    "type": pattern["id"],
                    "name": pattern["name"],
                    "diagnosis": pattern["diagnosis"],
                    "solutions": pattern["solutions"]
                })
        
        while len(self._result_cache) >= self._cache_max_size:
            self._result_cache.popitem(last=False)
        
        self._result_cache[log_hash] = results
        
        return results

    def learn_solution(self, crash_signature, solution):
        self.learning_data["user_solutions"].append({
            "signature": crash_signature,
            "solution": solution,
            "timestamp": str(datetime.now())
        })
        self._save_learning_data()

    def _save_learning_data(self):
        try:
            with open(self.learning_data_file, 'w', encoding='utf-8') as f:
                json.dump(self.learning_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save learning data: {e}")
