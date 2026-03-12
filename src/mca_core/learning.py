from __future__ import annotations
import json
import os
import re
import logging
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any
import threading
from datetime import datetime

from config.constants import AI_SEMANTIC_LIMIT

MAX_PATTERNS = 500
MIN_HIT_COUNT = 2
FEATURE_WEIGHTS = {
    "trait": 3.0,
    "exception": 2.5,
    "stack": 1.5,
    "mod": 2.0,
    "loader": 1.8,
    "java": 1.5,
    "version": 1.2,
    "memory": 1.0,
    "default": 1.0,
}

_RE_EXCEPTIONS = re.compile(r'(?:^|[\s.:])([a-zA-Z0-9_\.$]+(?:Exception|Error))')
_RE_STACK_LINES = re.compile(r'\s+at ([a-zA-Z0-9_\.$]+)\(')
_RE_MOD_ID = re.compile(r"(?:mod\s+id[:\s]+|modid[:\s]+)([a-zA-Z0-9_\-]+)", re.IGNORECASE)
_RE_VERSION = re.compile(r"version[:\s]+([0-9]+\.[0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
_RE_JAVA_VERSION = re.compile(r"java\s*(?:version|runtime)?[:\s]*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
_RE_MEMORY = re.compile(r"(?:allocated|memory|heap)[:\s]*([0-9]+)\s*(?:mb|gb|mib|gib)?", re.IGNORECASE)
_RE_ERROR_CODE = re.compile(r"(?:error|err|exception)[:\s]*([A-Z0-9_]{3,})", re.IGNORECASE)
_RE_THREAD_NAME = re.compile(r"\[(\w+(?:-\d+)?)\]/", re.MULTILINE)
_RE_CLASS_NAME = re.compile(r"([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+)\.[A-Z][a-zA-Z0-9_]*")

_CRITICAL_PATTERNS = [
    (re.compile(r"missing (?:mod|dependency|requirement)"), "missing_dep"),
    (re.compile(r"opengl (?:error|invalid)"), "gl_error"),
    (re.compile(r"glfw error"), "glfw_error"),
    (re.compile(r"mixin apply failed"), "mixin_error"),
    (re.compile(r"incompatible"), "incompatible"),
    (re.compile(r"version conflict"), "ver_conflict"),
    (re.compile(r"failed to load"), "load_fail"),
    (re.compile(r"out of memory|oom|heap space"), "oom_error"),
    (re.compile(r"access violation|segfault|crash"), "native_crash"),
    (re.compile(r"shader(?:s)?\s+(?:compil|load|error)"), "shader_error"),
    (re.compile(r"texture\s+(?:error|missing|failed)"), "texture_error"),
    (re.compile(r"world\s+(?:corrupt|error|failed)"), "world_error"),
    (re.compile(r"saves?\s+(?:corrupt|error|failed)"), "save_error"),
    (re.compile(r"config(?:uration)?\s+(?:error|invalid|missing)"), "config_error"),
    (re.compile(r"json\s+(?:parse|syntax|error)"), "json_error"),
    (re.compile(r"network\s+(?:error|timeout|connection)"), "network_error"),
    (re.compile(r"class\s+not\s+found"), "class_not_found"),
    (re.compile(r"no\s+such\s+method"), "no_such_method"),
    (re.compile(r"illegal\s+(?:argument|state)"), "illegal_state"),
    (re.compile(r"null\s*pointer"), "npe"),
    (re.compile(r"concurrent\s+modification"), "concurrent_mod"),
    (re.compile(r"security\s+(?:exception|violation)"), "security"),
    (re.compile(r"file\s+not\s+found"), "file_not_found"),
    (re.compile(r"permission\s+denied"), "permission_denied"),
]


@dataclass
class Solution:
    text: str
    confidence: float = 0.0


class FeedbackSystem:
    def record(self, pattern_id: str, success: bool) -> None:
        return


class CrashPatternLearner:
    """崩溃模式学习器，支持智能模式匹配和学习。
    
    增强功能：
    - 加权特征提取和相似度计算
    - 增量学习支持
    - 模式持久化
    - 语义引擎接口
    """
    
    def __init__(self, storage_path: str, max_patterns: int = MAX_PATTERNS) -> None:
        self.storage_path = storage_path
        self.max_patterns = max_patterns
        self._patterns: list[dict[str, Any]] = self._load_patterns()
        self._feedback_system = FeedbackSystem()
        self.similarity_threshold = 0.5
        self._lock = threading.RLock()
        self.semantic_encoder = None
        self.semantic_comparator = None
        self._store_embeddings = True
        self._pattern_index: dict[str, int] = {}
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        """重建模式索引以加速查找。"""
        self._pattern_index.clear()
        for i, p in enumerate(self._patterns):
            key = self._compute_pattern_key(p.get("features", []))
            if key:
                self._pattern_index[key] = i

    def _compute_pattern_key(self, features: list[str]) -> str | None:
        """计算模式的快速查找键。"""
        traits = sorted([f for f in features if f.startswith("trait:")])
        exceptions = sorted([f for f in features if f.startswith("exception:")])[:2]
        if traits or exceptions:
            return "|".join(traits + exceptions)
        return None

    def set_semantic_engine(self, encoder: Any, comparator: Any) -> None:
        self.semantic_encoder = encoder
        self.semantic_comparator = comparator

    def set_store_embeddings(self, enabled: bool) -> None:
        self._store_embeddings = enabled
        if not enabled:
            with self._lock:
                for p in self._patterns:
                    p.pop("embedding", None)
                self._save_patterns()

    def _load_patterns(self) -> list[dict[str, Any]]:
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logging.getLogger(__name__).warning(f"Failed to load patterns: {e}")
        return []

    def _save_patterns(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            patterns_to_save = []
            for p in self._patterns:
                clean_pattern = {k: v for k, v in p.items() if not k.startswith('_')}
                patterns_to_save.append(clean_pattern)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(patterns_to_save, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to save patterns: {e}")

    def _prune_patterns(self) -> None:
        if len(self._patterns) <= self.max_patterns:
            return
        self._patterns.sort(key=lambda p: p.get("hit_count", 0), reverse=True)
        removed = len(self._patterns) - self.max_patterns
        self._patterns = self._patterns[:self.max_patterns]
        self._rebuild_index()
        if removed > 0:
            logging.getLogger(__name__).debug(f"Pruned {removed} low-activity patterns")

    _MAX_EXTRACT_BYTES: int = 512 * 1024

    def _extract_features(self, crash_log: str) -> list[str]:
        if not crash_log:
            return []
        if len(crash_log) > self._MAX_EXTRACT_BYTES:
            crash_log = crash_log[:self._MAX_EXTRACT_BYTES]

        features = []
        lower_log = crash_log.lower()

        exceptions = _RE_EXCEPTIONS.findall(crash_log)
        for exc in exceptions[:10]:
            features.append(f"exception:{exc}")

        stack_lines = _RE_STACK_LINES.findall(crash_log)
        for stack in stack_lines[:15]:
            parts = stack.rsplit('.', 1)
            if len(parts) > 1:
                features.append(f"stack:{parts[0]}")

        for pattern, label in _CRITICAL_PATTERNS:
            if pattern.search(lower_log):
                features.append(f"trait:{label}")

        mod_ids = _RE_MOD_ID.findall(crash_log)
        for mod_id in mod_ids[:5]:
            features.append(f"mod:{mod_id.lower()}")

        versions = _RE_VERSION.findall(crash_log)
        for ver in versions[:3]:
            features.append(f"version:{ver}")

        java_vers = _RE_JAVA_VERSION.findall(crash_log)
        if java_vers:
            features.append(f"java:{java_vers[0]}")

        mem_matches = _RE_MEMORY.findall(crash_log)
        for mem in mem_matches[:2]:
            features.append(f"memory:{mem}")

        if "neoforge" in lower_log:
            features.append("loader:neoforge")
        elif "forge" in lower_log and "fml" in lower_log:
            features.append("loader:forge")
        elif "fabric" in lower_log and "quilt" not in lower_log:
            features.append("loader:fabric")
        elif "quilt" in lower_log:
            features.append("loader:quilt")

        error_codes = _RE_ERROR_CODE.findall(crash_log)
        for code in error_codes[:3]:
            features.append(f"error_code:{code.upper()}")

        thread_names = _RE_THREAD_NAME.findall(crash_log)
        for thread in thread_names[:3]:
            if thread.lower() not in ("main", "thread", "server", "client"):
                features.append(f"thread:{thread.lower()}")

        class_names = _RE_CLASS_NAME.findall(crash_log)
        seen_packages = set()
        for cls in class_names[:10]:
            pkg = cls.split('.')[0] if '.' in cls else cls
            if pkg not in seen_packages and pkg not in ("java", "javax", "sun", "com", "org"):
                seen_packages.add(pkg)
                features.append(f"pkg:{pkg}")

        return list(set(features))

    def _get_feature_weight(self, feature: str) -> float:
        if feature.startswith("trait:"):
            return FEATURE_WEIGHTS["trait"]
        elif feature.startswith("exception:"):
            return FEATURE_WEIGHTS["exception"]
        elif feature.startswith("stack:"):
            return FEATURE_WEIGHTS["stack"]
        elif feature.startswith("mod:"):
            return FEATURE_WEIGHTS["mod"]
        elif feature.startswith("loader:"):
            return FEATURE_WEIGHTS["loader"]
        elif feature.startswith("java:"):
            return FEATURE_WEIGHTS["java"]
        elif feature.startswith("version:"):
            return FEATURE_WEIGHTS["version"]
        elif feature.startswith("memory:"):
            return FEATURE_WEIGHTS["memory"]
        return FEATURE_WEIGHTS["default"]

    def _calculate_weighted_similarity(self, features1: list[str], features2: list[str]) -> float:
        if not features1 or not features2:
            return 0.0

        f1 = set(features1)
        f2 = set(features2)
        intersection = f1.intersection(f2)
        
        if not intersection:
            return 0.0

        weighted_intersection = sum(self._get_feature_weight(f) for f in intersection)
        weighted_union = sum(self._get_feature_weight(f) for f in f1.union(f2))
        
        if weighted_union == 0:
            return 0.0

        base_score = weighted_intersection / weighted_union

        trait_matches = sum(1 for f in intersection if f.startswith("trait:"))
        exception_matches = sum(1 for f in intersection if f.startswith("exception:"))

        bonus = 0.0
        if trait_matches > 0:
            bonus += 0.1 * min(trait_matches, 3)
        if exception_matches > 0:
            bonus += 0.05 * min(exception_matches, 2)

        return min(base_score + bonus, 1.0)

    def _calculate_similarity(self, features1: list[str], features2: list[str]) -> float:
        return self._calculate_weighted_similarity(features1, features2)

    def _find_similar_pattern(
        self,
        features: list[str],
        vector: list[float] | None = None
    ) -> tuple[dict[str, Any] | None, float]:
        with self._lock:
            best_score = 0.0
            best_match = None

            query_features_set = set(features)
            if not query_features_set:
                return None, 0.0

            quick_key = self._compute_pattern_key(features)
            if quick_key and quick_key in self._pattern_index:
                idx = self._pattern_index[quick_key]
                p = self._patterns[idx]
                stored_features = p.get("features", [])
                base_score = self._calculate_similarity(features, stored_features)
                if base_score > 0.8:
                    return p, base_score

            for p in self._patterns:
                stored_features = p.get("features", [])
                base_score = self._calculate_similarity(features, stored_features)
                final_score = base_score

                if vector and self.semantic_comparator and "embedding" in p:
                    stored_vector = p["embedding"]
                    sem_score = self.semantic_comparator(vector, stored_vector)
                    final_score = (base_score * 0.4) + (sem_score * 0.6)

                if final_score > best_score:
                    best_score = final_score
                    best_match = p

            return best_match, best_score

    def get_pattern_count(self) -> int:
        with self._lock:
            return len(self._patterns)

    def get_memory_usage(self) -> dict[str, int | float]:
        with self._lock:
            pattern_count = len(self._patterns)
            embedding_count = sum(1 for p in self._patterns if "embedding" in p)
            estimated_embedding_mem = embedding_count * 4 * 1024
            return {
                "pattern_count": pattern_count,
                "embedding_count": embedding_count,
                "estimated_embedding_bytes": estimated_embedding_mem,
                "max_patterns": self.max_patterns
            }

    def learn_from_crash(self, crash_log: str, analysis_result: list[str]) -> None:
        if not crash_log or not analysis_result:
            return

        features = self._extract_features(crash_log)
        if not features:
            return

        vector = None
        if self.semantic_encoder and self._store_embeddings:
            vector = self.semantic_encoder(crash_log[:AI_SEMANTIC_LIMIT])

        with self._lock:
            match, score = self._find_similar_pattern(features, vector)

            if match and score >= self.similarity_threshold:
                match["result"] = analysis_result
                match["hit_count"] = match.get("hit_count", 0) + 1
                match["last_hit"] = datetime.now().isoformat()
                if vector and self._store_embeddings:
                    match["embedding"] = vector
            else:
                new_pattern: dict[str, Any] = {
                    "features": features,
                    "result": analysis_result,
                    "hit_count": 1,
                    "created": datetime.now().isoformat(),
                    "last_hit": datetime.now().isoformat(),
                }
                if vector and self._store_embeddings:
                    new_pattern["embedding"] = vector
                self._patterns.append(new_pattern)
                self._rebuild_index()

            self._prune_patterns()
            self._save_patterns()

    def suggest_solutions(self, crash_log: str) -> list[Solution]:
        if not self._patterns:
            return []

        features = self._extract_features(crash_log)

        vector = None
        if self.semantic_encoder and self._store_embeddings:
            vector = self.semantic_encoder(crash_log[:AI_SEMANTIC_LIMIT])

        with self._lock:
            match, score = self._find_similar_pattern(features, vector)

            threshold = self.similarity_threshold
            if vector and self.semantic_comparator:
                threshold = 0.45

            if match and score >= threshold:
                res_list = match.get("result", [])

                if not res_list:
                    return []

                filtered_res = [
                    line.strip() for line in res_list
                    if line.strip() and "扫描完成" not in line and "Mod总数" not in line and "加载器" not in line
                ]

                if filtered_res:
                    detail_res = [
                        line for line in filtered_res
                        if re.search(r"(缺失|依赖|需要|前置|->|MOD|mod|冲突|不兼容|conflict|required)", line, re.IGNORECASE)
                    ]

                    other_critical = [
                        line for line in filtered_res
                        if re.search(r"(重复|duplicate|opengl|glfw|driver)", line, re.IGNORECASE)
                    ]

                    final_picks: list[str] = []
                    seen: set[str] = set()
                    for item in detail_res + other_critical:
                        if item not in seen:
                            final_picks.append(item)
                            seen.add(item)

                    if not final_picks:
                        final_picks = filtered_res[:5]
                    else:
                        final_picks = final_picks[:10]

                    summary_text = "\n".join(final_picks)
                    method = "AI 深度理解" if vector else "关键特征匹配"

                    if vector:
                        logging.getLogger(__name__).debug(
                            f"AI Diagnosis Match Score: {score:.4f} (Threshold: {threshold})"
                        )

                    return [Solution(
                        text=f"[{method} {score:.0%}] 历史修复建议:\n{summary_text}",
                        confidence=score
                    )]

        return []

    def batch_learn(self, crash_data: list[tuple[str, list[str]]]) -> int:
        """批量学习崩溃模式，返回成功学习的数量。"""
        learned = 0
        for crash_log, analysis_result in crash_data:
            try:
                self.learn_from_crash(crash_log, analysis_result)
                learned += 1
            except Exception as e:
                logging.getLogger(__name__).warning(f"Batch learn failed: {e}")
        return learned

    def export_patterns(self, export_path: str) -> bool:
        """导出模式到指定路径。"""
        try:
            with self._lock:
                with open(export_path, "w", encoding="utf-8") as f:
                    json.dump(self._patterns, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logging.getLogger(__name__).error(f"Export patterns failed: {e}")
            return False

    def import_patterns(self, import_path: str, merge: bool = True) -> int:
        """导入模式，返回导入的数量。"""
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                imported = json.load(f)

            with self._lock:
                if not merge:
                    self._patterns = imported
                else:
                    existing_keys = set()
                    for p in self._patterns:
                        key = self._compute_pattern_key(p.get("features", []))
                        if key:
                            existing_keys.add(key)

                    for p in imported:
                        key = self._compute_pattern_key(p.get("features", []))
                        if key and key not in existing_keys:
                            self._patterns.append(p)
                            existing_keys.add(key)

                self._prune_patterns()
                self._rebuild_index()
                self._save_patterns()

            return len(imported)
        except Exception as e:
            logging.getLogger(__name__).error(f"Import patterns failed: {e}")
            return 0

    def get_statistics(self) -> dict[str, Any]:
        """获取学习器统计信息。"""
        with self._lock:
            total_hits = sum(p.get("hit_count", 0) for p in self._patterns)
            avg_hits = total_hits / len(self._patterns) if self._patterns else 0

            trait_counts: Counter = Counter()
            for p in self._patterns:
                for f in p.get("features", []):
                    if f.startswith("trait:"):
                        trait_counts[f[6:]] += 1

            return {
                "total_patterns": len(self._patterns),
                "max_patterns": self.max_patterns,
                "total_hits": total_hits,
                "average_hits": round(avg_hits, 2),
                "top_traits": trait_counts.most_common(10),
                "embedding_enabled": self._store_embeddings,
                "semantic_engine_enabled": self.semantic_encoder is not None,
            }
