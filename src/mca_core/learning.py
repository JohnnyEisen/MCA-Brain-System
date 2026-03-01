from __future__ import annotations
import json
import os
import re
from dataclasses import dataclass
from typing import Any
import threading

from config.constants import AI_SEMANTIC_LIMIT

# 模式学习器配置
MAX_PATTERNS = 500  # 最大模式数量
MIN_HIT_COUNT = 2   # 最小命中次数（低于此值的模式可能被淘汰）

# [Optimization] 预编译正则以极大提升传统算力（降低 CPU 开销）
_RE_EXCEPTIONS = re.compile(r'(?:^|[\s.:])([a-zA-Z0-9_\.$]+(?:Exception|Error))')
_RE_STACK_LINES = re.compile(r'\s+at ([a-zA-Z0-9_\.$]+)\(')
_CRITICAL_PATTERNS = [
    (re.compile(r"missing (?:mod|dependency|requirement)"), "missing_dep"),
    (re.compile(r"opengl (?:error|invalid)"), "gl_error"),
    (re.compile(r"glfw error"), "glfw_error"),
    (re.compile(r"mixin apply failed"), "mixin_error"),
    (re.compile(r"incompatible"), "incompatible"),
    (re.compile(r"version conflict"), "ver_conflict"),
    (re.compile(r"failed to load"), "load_fail"),
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
    
    内存优化：
    - 模式数量上限 (MAX_PATTERNS)
    - 基于命中次数的淘汰机制
    - 向量存储可选（可禁用以节省内存）
    """
    
    def __init__(self, storage_path: str, max_patterns: int = MAX_PATTERNS) -> None:
        self.storage_path = storage_path
        self.max_patterns = max_patterns
        self._patterns: list[dict[str, Any]] = self._load_patterns()
        self._feedback_system = FeedbackSystem()
        self.similarity_threshold = 0.6  # 相似度阈值
        self._lock = threading.RLock()
        
        # 语义引擎接口 (Plugin/DLC 注入)
        self.semantic_encoder = None
        self.semantic_comparator = None
        
        # 是否存储 embedding（内存优化：可禁用）
        self._store_embeddings = True

    def set_semantic_engine(self, encoder: Any, comparator: Any) -> None:
        """注入基于 AI 的语义分析引擎。"""
        self.semantic_encoder = encoder
        self.semantic_comparator = comparator

    def set_store_embeddings(self, enabled: bool) -> None:
        """设置是否存储语义向量（禁用可节省内存）。"""
        self._store_embeddings = enabled
        if not enabled:
            # 清除现有 embeddings
            with self._lock:
                for p in self._patterns:
                    p.pop("embedding", None)
                self._save_patterns()

    def _load_patterns(self) -> list[dict[str, Any]]:
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_patterns(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self._patterns, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save patterns: {e}")

    def _prune_patterns(self) -> None:
        """淘汰低效模式，保持模式数量在限制内。"""
        if len(self._patterns) <= self.max_patterns:
            return
        
        # 按命中次数排序，保留高频模式
        self._patterns.sort(key=lambda p: p.get("hit_count", 0), reverse=True)
        
        # 保留 top max_patterns
        removed = len(self._patterns) - self.max_patterns
        self._patterns = self._patterns[:self.max_patterns]
        
        if removed > 0:
            print(f"DEBUG: Pruned {removed} low-activity patterns")

    # Max input length for regex feature extraction to prevent ReDoS (V-007)
    _MAX_EXTRACT_BYTES: int = 512 * 1024  # 512KB

    def _extract_features(self, crash_log: str) -> list[str]:
        """提取特征：包含异常类型、堆栈位置、关键错误描述。"""
        if not crash_log:
            return []

        # V-007 Fix: Limit input size to prevent ReDoS
        if len(crash_log) > self._MAX_EXTRACT_BYTES:
            crash_log = crash_log[:self._MAX_EXTRACT_BYTES]

        # 1. 提取异常类名 (Java Exceptions)
        exceptions = _RE_EXCEPTIONS.findall(crash_log)
        
        # 2. 提取堆栈关键行 (Stack Trace)
        # 排除 native method 和 unknown source，只取有明确类名的方法
        stack_lines = _RE_STACK_LINES.findall(crash_log)
        
        # 3. 提取关键语义短语 (Critical Phrases)
        # 这对于没有堆栈的错误（如 Mod 缺失、OpenGL 错误）至关重要
        phrases = []
        lower_log = crash_log.lower()
        
        for pattern, label in _CRITICAL_PATTERNS:
            if pattern.search(lower_log):
                phrases.append(f"trait:{label}")

        # 组合特征：
        # - 语义特征 (Trait) 权重高，放在前面
        # - 异常类名 (Exception)
        # - 堆栈 (Stack) 取前 15 行，避免通用框架代码干扰
        
        features = list(set(phrases + exceptions + stack_lines[:15]))
        return features

    def _calculate_similarity(self, features1: list[str], features2: list[str]) -> float:
        """计算 Jaccard 相似度。"""
        s1 = set(features1)
        s2 = set(features2)
        if not s1 or not s2:
            return 0.0
        intersection = len(s1.intersection(s2))
        union = len(s1.union(s2))
        return intersection / union

    def _find_similar_pattern(
        self,
        features: list[str],
        vector: list[float] | None = None
    ) -> tuple[dict[str, Any] | None, float]:
        with self._lock:
            best_score = 0.0
            best_match = None
            
            # [Optimization] 预先转换 set 以避免在循环中重复创建，大幅提升匹配效率
            query_features_set = set(features)
            if not query_features_set:
                return None, 0.0
            
            for p in self._patterns:
                # 1. 传统特征匹配
                stored_features = p.get("features", [])
                # 快速计算 Jaccard 相似度 (避免函数调用开销和额外的 set() 转换)
                stored_set = p.get("_cached_set")
                if stored_set is None:
                    stored_set = set(stored_features)
                    p["_cached_set"] = stored_set
                    
                if not stored_set:
                    base_score = 0.0
                else:
                    intersection = len(query_features_set.intersection(stored_set))
                    union = len(query_features_set.union(stored_set))
                    base_score = intersection / union if union > 0 else 0.0
                final_score = base_score

                # 2. 语义向量匹配 (如果启用)
                if vector and self.semantic_comparator and "embedding" in p:
                    stored_vector = p["embedding"]
                    sem_score = self.semantic_comparator(vector, stored_vector)
                    # 混合权重: 40% 传统 + 60% 语义
                    final_score = (base_score * 0.4) + (sem_score * 0.6)

                if final_score > best_score:
                    best_score = final_score
                    best_match = p
            
            return best_match, best_score

    def get_pattern_count(self) -> int:
        with self._lock:
            return len(self._patterns)

    def get_memory_usage(self) -> dict[str, int | float]:
        """返回内存使用估算（用于调试/监控）。"""
        with self._lock:
            pattern_count = len(self._patterns)
            embedding_count = sum(1 for p in self._patterns if "embedding" in p)
            # 估算每个 embedding 约 4KB (假设 1024 维 float32)
            estimated_embedding_mem = embedding_count * 4 * 1024
            return {
                "pattern_count": pattern_count,
                "embedding_count": embedding_count,
                "estimated_embedding_bytes": estimated_embedding_mem,
                "max_patterns": self.max_patterns
            }

    def learn_from_crash(self, crash_log: str, analysis_result: list[str]) -> None:
        """学习新的崩溃模式。"""
        if not crash_log or not analysis_result:
            return

        features = self._extract_features(crash_log)
        if not features:
            return

        # 计算语义向量
        vector = None
        if self.semantic_encoder and self._store_embeddings:
            vector = self.semantic_encoder(crash_log[:AI_SEMANTIC_LIMIT])

        with self._lock:
            match, score = self._find_similar_pattern(features, vector)
            
            if match and score >= self.similarity_threshold:
                # 更新已有模式
                match["result"] = analysis_result
                match["hit_count"] = match.get("hit_count", 0) + 1
                if vector and self._store_embeddings:
                    match["embedding"] = vector  # 更新向量
            else:
                # 创建新模式
                new_pattern: dict[str, Any] = {
                    "features": features,
                    "result": analysis_result,
                    "hit_count": 1,
                }
                if vector and self._store_embeddings:
                    new_pattern["embedding"] = vector
                self._patterns.append(new_pattern)
            
            # 淘汰低效模式
            self._prune_patterns()
            self._save_patterns()

    def suggest_solutions(self, crash_log: str) -> list[Solution]:
        if not self._patterns:
            return []
        
        features = self._extract_features(crash_log)
        
        vector = None
        if self.semantic_encoder and self._store_embeddings:
            # 缩减语义分析的输入长度以提高性能，同时避免噪声
            vector = self.semantic_encoder(crash_log[:AI_SEMANTIC_LIMIT])

        with self._lock:
            match, score = self._find_similar_pattern(features, vector)
            
            # 动态阈值：如果是深度语义匹配，阈值稍高；如果是传统匹配，阈值适中
            threshold = self.similarity_threshold
            # 如果启用了语义引擎，我们稍微放宽阈值，因为向量相似度通常比 Jaccard 更鲁棒但数值偏低
            if vector and self.semantic_comparator:
                threshold = 0.55
            
            if match and score >= threshold:
                res_list = match.get("result", [])
                
                # --- 用户反馈修复：AI 模式下结果变少问题 ---
                # A. 过滤空结果
                if not res_list: 
                    return []
                
                # B. 更智能的结果筛选
                # 之前过滤 ">>" 可能剔除了部分关键小标题，导致上下文丢失
                filtered_res = [
                    line.strip() for line in res_list 
                    if line.strip() and "扫描完成" not in line and "Mod总数" not in line and "加载器" not in line
                ]

                if filtered_res:
                    # 优先展示缺失依赖/具体模组的细节行
                    detail_res = [
                        line for line in filtered_res 
                        if re.search(r"(缺失|依赖|需要|前置|->|MOD|mod|冲突|不兼容|conflict|required)", line, re.IGNORECASE)
                    ]
                    
                    # 补充: 如果有 "重复MOD" 或 "GL错误" 关键词也加上
                    other_critical = [
                        line for line in filtered_res 
                        if re.search(r"(重复|duplicate|opengl|glfw|driver)", line, re.IGNORECASE)
                    ]
                    
                    # 合并并去重
                    final_picks: list[str] = []
                    seen: set[str] = set()
                    for item in detail_res + other_critical:
                        if item not in seen:
                            final_picks.append(item)
                            seen.add(item)

                    # 如果没有匹配到细节，回退到取前几行
                    if not final_picks:
                        final_picks = filtered_res[:5]
                    else:
                        # 限制显示数量，防止AI建议过长
                        final_picks = final_picks[:10]

                    summary_text = "\n".join(final_picks)
                    method = "AI 深度理解" if vector else "关键特征匹配"
                    
                    # 调试日志：如果使用了语义向量，打印置信度
                    if vector:
                        print(f"DEBUG: AI Diagnosis Match Score: {score:.4f} (Threshold: {threshold})")

                    return [Solution(
                        text=f"[{method} {score:.0%}] 历史修复建议:\n{summary_text}", 
                        confidence=score
                    )]
        
        return []
