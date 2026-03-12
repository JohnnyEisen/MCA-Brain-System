import json
import os
import re
import logging
from datetime import datetime
from mca_core.pattern_repository import get_repository, PatternRepository
from mca_core.regex_cache import RegexCache

logger = logging.getLogger(__name__)

class DiagnosticEngine:
    def __init__(self, data_dir: str, repo: PatternRepository | None = None) -> None:
        self.data_dir = data_dir
        # 如果外部没有注入 repo，则默认使用 JSON 实现 (v1.2 兼容)
        if repo:
            self.repo = repo
        else:
            rules_path = os.path.join(data_dir, "diagnostic_rules.json")
            self.repo = get_repository("json", rules_path)
            
        self.learning_data_file = os.path.join(data_dir, "learning_data.json")
        # Learning data 也可以复刻这个 Repository 模式，但暂时保持原样
        self.learning_data = self._load_learning_data()

        # Load rules via the repository abstraction
        self.rules = self._load_rules_safely()

    def _load_rules_safely(self):
        """
        从 Repository 加载规则。
        不再处理文件 IO 异常，这些都由 Repository 层负责。
        """
        patterns = self.repo.load_all_patterns()
        if not patterns:
            # 如果是空的（首次运行），创建默认规则
            defaults = self._create_default_rules()
            # 存回仓库（初始化）
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
                    "regex": ["Tessellating block model", "Rendering entity", "OpenGL Error", "Exit code -1073741819"],
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
                }
            ]
        }
        # 规则已通过 repo.save_pattern() 保存，无需额外保存
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
        """分析崩溃日志，返回匹配的诊断结果。"""
        results: list[dict[str, str | list[str]]] = []
        for pattern in self.rules.get("patterns", []):
            for regex in pattern.get("regex", []):
                # 使用 RegexCache 预编译正则，提升性能
                if RegexCache.search(regex, crash_log, flags=re.IGNORECASE):
                    results.append({
                        "type": pattern["id"],
                        "name": pattern["name"],
                        "diagnosis": pattern["diagnosis"],
                        "solutions": pattern["solutions"]
                    })
                    break  # 每个模式只匹配一次
        
        return results

    def learn_solution(self, crash_signature, solution):
        """
        Record a user-provided solution for a specific crash signature.
        """
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
