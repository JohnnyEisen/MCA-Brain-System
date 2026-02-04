from __future__ import annotations
import json
import os
import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


import threading

from config.constants import AI_SEMANTIC_LIMIT

@dataclass
class Solution:
    text: str
    confidence: float = 0.0


class FeedbackSystem:
    def record(self, pattern_id: str, success: bool) -> None:
        return


class CrashPatternLearner:
    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self._patterns: List[Dict[str, Any]] = self._load_patterns()
        self._feedback_system = FeedbackSystem()
        self.similarity_threshold = 0.6  # 相似度阈值
        self._lock = threading.RLock()
        
        # 语义引擎接口 (Plugin/DLC 注入)
        self.semantic_encoder = None
        self.semantic_comparator = None

    def set_semantic_engine(self, encoder, comparator):
        """注入基于 AI 的语义分析引擎。"""
        self.semantic_encoder = encoder
        self.semantic_comparator = comparator

    def _load_patterns(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_patterns(self):
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self._patterns, f, ensure_ascii=False, indent=2)
            
            # 记录到自动化测试日志 (如果存在上下文)
            # 通过检查栈帧或传递回调可能太复杂，这里简化处理，不做强耦合
        except Exception as e:
            print(f"Failed to save patterns: {e}")

    def _extract_features(self, crash_log: str) -> List[str]:

        """提取特征：包含异常类型、堆栈位置、关键错误描述。"""
        if not crash_log:
            return []
        
        # 1. 提取异常类名 (Java Exceptions)
        exceptions = re.findall(r'(?:^|[\s.:])([a-zA-Z0-9_\.$]+(?:Exception|Error))', crash_log)
        
        # 2. 提取堆栈关键行 (Stack Trace)
        # 排除 native method 和 unknown source，只取有明确类名的方法
        stack_lines = re.findall(r'\s+at ([a-zA-Z0-9_\.$]+)\(', crash_log)
        
        # 3. 提取关键语义短语 (Critical Phrases)
        # 这对于没有堆栈的错误（如 Mod 缺失、OpenGL 错误）至关重要
        phrases = []
        lower_log = crash_log.lower()
        
        critical_patterns = [
            (r"missing (?:mod|dependency|requirement)", "missing_dep"),
            (r"opengl (?:error|invalid)", "gl_error"),
            (r"glfw error", "glfw_error"),
            (r"mixin apply failed", "mixin_error"),
            (r"incompatible", "incompatible"),
            (r"version conflict", "ver_conflict"),
            (r"failed to load", "load_fail"),
        ]
        
        for p, label in critical_patterns:
            if re.search(p, lower_log):
                phrases.append(f"trait:{label}")

        # 组合特征：
        # - 语义特征 (Trait) 权重高，放在前面
        # - 异常类名 (Exception)
        # - 堆栈 (Stack) 取前 15 行，避免通用框架代码干扰
        
        features = list(set(phrases + exceptions + stack_lines[:15]))
        return features

    def _calculate_similarity(self, features1: List[str], features2: List[str]) -> float:
        """计算 Jaccard 相似度。"""
        s1 = set(features1)
        s2 = set(features2)
        if not s1 or not s2:
            return 0.0
        intersection = len(s1.intersection(s2))
        union = len(s1.union(s2))
        return intersection / union

    def _find_similar_pattern(self, features: List[str], vector: Optional[List[float]] = None) -> tuple[Optional[Dict[str, Any]], float]:
        with self._lock:
            best_score = 0.0
            best_match = None
            
            for p in self._patterns:
                # 1. 传统特征匹配
                stored_features = p.get("features", [])
                base_score = self._calculate_similarity(features, stored_features)
                
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

    def learn_from_crash(self, crash_log: str, analysis_result: List[str]):
        """学习新的崩溃模式。"""
        if not crash_log or not analysis_result:
            return

        features = self._extract_features(crash_log)
        if not features:
            return

        # 计算语义向量
        vector = None
        if self.semantic_encoder:
            vector = self.semantic_encoder(crash_log[:AI_SEMANTIC_LIMIT])

        with self._lock:
            match, score = self._find_similar_pattern(features, vector)
            
            if match and score >= self.similarity_threshold:
                # 更新已有模式
                match["result"] = analysis_result
                match["hit_count"] = match.get("hit_count", 0) + 1
                if vector:
                    match["embedding"] = vector # 更新向量
            else:
                # 创建新模式
                new_pattern = {
                    "features": features,
                    "result": analysis_result,
                    "hit_count": 1,
                }
                if vector:
                    new_pattern["embedding"] = vector
                self._patterns.append(new_pattern)
            
            self._save_patterns()

    def suggest_solutions(self, crash_log: str) -> List[Solution]:
        if not self._patterns:
            return []
        
        features = self._extract_features(crash_log)
        
        vector = None
        if self.semantic_encoder:
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
                if not res_list: return []
                
                # B. 更智能的结果筛选
                # 之前过滤 ">>" 可能剔除了部分关键小标题，导致上下文丢失
                filtered_res = [
                    line.strip() for line in res_list 
                    if line.strip() and "扫描完成" not in line and "Mod总数" not in line and "加载器" not in line
                ]

                if filtered_res:
                    # 优先展示缺失依赖/具体模组的细节行
                    detail_res = [line for line in filtered_res if re.search(r"(缺失|依赖|需要|前置|->|MOD|mod|冲突|不兼容|conflict|required)", line, re.IGNORECASE)]
                    
                    # 补充: 如果有 "重复MOD" 或 "GL错误" 关键词也加上
                    other_critical = [line for line in filtered_res if re.search(r"(重复|duplicate|opengl|glfw|driver)", line, re.IGNORECASE)]
                    
                    # 合并并去重
                    final_picks = []
                    seen = set()
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
                         # 使用 logging 或 print 记录到控制台
                         print(f"DEBUG: AI Diagnosis Match Score: {score:.4f} (Threshold: {threshold})")

                    return [Solution(
                        text=f"[{method} {score:.0%}] 历史修复建议:\n{summary_text}", 
                        confidence=score
                    )]
        
        return []
