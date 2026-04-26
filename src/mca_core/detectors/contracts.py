"""
检测器契约模块

定义检测器和分析上下文的数据结构。

类说明:
    - DetectionResult: 单个检测结果数据类
    - AnalysisContext: 分析上下文，管理检测过程状态
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from threading import RLock


@dataclass
class DetectionResult:
    """
    检测结果数据类。
    
    存储单个检测器的检测结果。
    
    Attributes:
        message: 检测结果消息
        detector: 检测器名称
        cause_label: 关联的原因标签（可选）
        metadata: 额外元数据字典
    """
    
    message: str
    detector: str
    cause_label: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisContext:
    """
    分析上下文数据类。
    
    管理检测过程中的状态和结果收集。
    提供线程安全的结果添加方法。
    
    Attributes:
        analyzer: 分析器实例（提供 lock 和 analysis_results）
        crash_log: 崩溃日志文本
        results: 检测结果列表
        cause_counts: 原因统计字典
    
    方法:
        - add_result: 添加单个检测结果（线程安全）
        - add_result_block: 批量添加检测结果（线程安全）
    """
    
    analyzer: Any
    crash_log: str
    results: List[DetectionResult] = field(default_factory=list)
    cause_counts: Dict[str, int] = field(default_factory=dict)

    def _add_result_internal(
        self,
        message: str,
        detector: str,
        cause_label: Optional[str],
        metadata: Dict[str, Any]
    ) -> DetectionResult:
        """
        内部方法：添加结果（不获取锁，调用者必须持有锁）。
        
        Args:
            message: 结果消息
            detector: 检测器名称
            cause_label: 原因标签
            metadata: 元数据字典
            
        Returns:
            创建的检测结果
        """
        if self.analyzer and message:
            self.analyzer.analysis_results.append(message)
            if hasattr(self.analyzer, "_auto_test_write_log"):
                try:
                    self.analyzer._auto_test_write_log(
                        f"DEBUG: add_result matches: {detector} -> {cause_label}"
                    )
                except Exception:
                    pass

        if self.analyzer and cause_label:
            try:
                if hasattr(self.analyzer, "add_cause"):
                    self.analyzer.add_cause(cause_label)
                elif hasattr(self.analyzer, "_add_cause"):
                    self.analyzer._add_cause(cause_label)
            except Exception:
                pass

        if cause_label:
            self.cause_counts[cause_label] = self.cause_counts.get(cause_label, 0) + 1

        res = DetectionResult(
            message=message,
            detector=detector,
            cause_label=cause_label,
            metadata=metadata or {}
        )
        self.results.append(res)
        return res

    def add_result(
        self,
        message: str,
        detector: str,
        cause_label: Optional[str] = None,
        **metadata: Any
    ) -> DetectionResult:
        """
        添加单个检测结果（线程安全）。
        
        Args:
            message: 结果消息
            detector: 检测器名称
            cause_label: 原因标签（可选）
            **metadata: 额外元数据
            
        Returns:
            创建的检测结果
        """
        lock: Optional[RLock] = getattr(self.analyzer, "lock", None)
        if lock:
            with lock:
                return self._add_result_internal(message, detector, cause_label, metadata)
        else:
            return self._add_result_internal(message, detector, cause_label, metadata)

    def add_result_block(
        self,
        header: str,
        items: List[str],
        detector: str,
        cause_label: Optional[str] = None
    ) -> None:
        """
        批量添加检测结果（线程安全）。
        
        原子性地添加标题和多个条目，确保它们在输出中保持连续，
        防止与其他检测器的输出交错。
        
        Args:
            header: 块标题
            items: 条目列表
            detector: 检测器名称
            cause_label: 原因标签（可选）
        """
        lock: Optional[RLock] = getattr(self.analyzer, "lock", None)

        def _do_work() -> None:
            self._add_result_internal(header, detector, cause_label, {})
            for item in items:
                try:
                    self._add_result_internal(item, detector, None, {})
                except Exception:
                    pass

        if lock:
            with lock:
                _do_work()
        else:
            _do_work()
