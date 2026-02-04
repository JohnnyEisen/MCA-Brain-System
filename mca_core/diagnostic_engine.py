import json
import os
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class DiagnosticEngine:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.rules_file = os.path.join(data_dir, "diagnostic_rules.json")
        self.rules = self._load_rules()
        self.learning_data_file = os.path.join(data_dir, "learning_data.json")
        self.learning_data = self._load_learning_data()

    def _load_rules(self):
        if not os.path.exists(self.rules_file):
            return self._create_default_rules()
        try:
            with open(self.rules_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load diagnostic rules: {e}")
            return self._create_default_rules()

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
        self._save_rules(default_rules)
        return default_rules

    def _save_rules(self, rules):
        try:
            with open(self.rules_file, 'w', encoding='utf-8') as f:
                json.dump(rules, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save diagnostic rules: {e}")

    def _load_learning_data(self):
        if not os.path.exists(self.learning_data_file):
            return {"user_solutions": []}
        try:
            with open(self.learning_data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {"user_solutions": []}

    def analyze(self, crash_log):
        results = []
        for pattern in self.rules.get("patterns", []):
            for regex in pattern.get("regex", []):
                if re.search(regex, crash_log, re.IGNORECASE):
                    results.append({
                        "type": pattern["id"],
                        "name": pattern["name"],
                        "diagnosis": pattern["diagnosis"],
                        "solutions": pattern["solutions"]
                    })
                    break # Match each pattern only once
        
        # Check learning data for similar patterns (simplified)
        # In a real system, this would use more advanced similarity matching
        
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
