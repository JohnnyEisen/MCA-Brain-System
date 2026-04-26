"""
检测器性能监控模块

提供检测器执行性能监控和统计。

模块说明:
    本模块提供检测器性能监控功能，支持：
        - 执行时间统计
        - 成功/失败计数
        - 性能报告生成
        - 慢检测器告警
    
    主要组件:
        - DetectorMetrics: 检测器性能指标
        - PerformanceMonitor: 性能监控器
        - PerformanceReport: 性能报告
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DetectorMetrics:
    """
    单个检测器的性能指标。
    
    Attributes:
        name: 检测器名称
        call_count: 调用次数
        success_count: 成功次数
        error_count: 错误次数
        total_time_ms: 总执行时间（毫秒）
        min_time_ms: 最小执行时间
        max_time_ms: 最大执行时间
        last_error: 最后一次错误信息
        last_error_time: 最后一次错误时间
    """
    
    name: str
    call_count: int = 0
    success_count: int = 0
    error_count: int = 0
    total_time_ms: float = 0.0
    min_time_ms: float = float("inf")
    max_time_ms: float = 0.0
    last_error: Optional[str] = None
    last_error_time: Optional[float] = None
    
    @property
    def avg_time_ms(self) -> float:
        """平均执行时间。"""
        if self.call_count == 0:
            return 0.0
        return self.total_time_ms / self.call_count
    
    @property
    def success_rate(self) -> float:
        """成功率。"""
        if self.call_count == 0:
            return 0.0
        return self.success_count / self.call_count
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "name": self.name,
            "call_count": self.call_count,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": f"{self.success_rate:.2%}",
            "avg_time_ms": f"{self.avg_time_ms:.2f}",
            "min_time_ms": f"{self.min_time_ms:.2f}" if self.min_time_ms != float("inf") else "N/A",
            "max_time_ms": f"{self.max_time_ms:.2f}",
            "total_time_ms": f"{self.total_time_ms:.2f}",
            "last_error": self.last_error,
        }


@dataclass
class PerformanceReport:
    """
    性能报告。
    
    Attributes:
        start_time: 报告开始时间
        end_time: 报告结束时间
        total_analyses: 总分析次数
        total_detectors: 检测器数量
        metrics: 各检测器指标
    """
    
    start_time: float = field(default_factory=time.time)
    end_time: float = field(default_factory=time.time)
    total_analyses: int = 0
    total_detectors: int = 0
    metrics: Dict[str, DetectorMetrics] = field(default_factory=dict)
    
    @property
    def duration_seconds(self) -> float:
        """报告时长。"""
        return self.end_time - self.start_time
    
    def get_slow_detectors(self, threshold_ms: float = 1000.0) -> List[DetectorMetrics]:
        """
        获取慢检测器。
        
        Args:
            threshold_ms: 时间阈值（毫秒）
            
        Returns:
            超过阈值的检测器列表
        """
        return [
            m for m in self.metrics.values()
            if m.avg_time_ms > threshold_ms
        ]
    
    def get_error_detectors(self) -> List[DetectorMetrics]:
        """获取有错误的检测器。"""
        return [m for m in self.metrics.values() if m.error_count > 0]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": f"{self.duration_seconds:.2f}",
            "total_analyses": self.total_analyses,
            "total_detectors": self.total_detectors,
            "slow_detectors": [m.name for m in self.get_slow_detectors()],
            "error_detectors": [m.name for m in self.get_error_detectors()],
            "metrics": {k: v.to_dict() for k, v in self.metrics.items()},
        }


class PerformanceMonitor:
    """
    检测器性能监控器。
    
    收集检测器执行的性能数据，生成性能报告。
    
    Attributes:
        _metrics: 检测器指标字典
        _lock: 线程锁
        _start_time: 监控开始时间
        _analysis_count: 分析次数计数
    
    方法:
        - record: 记录检测结果
        - get_metrics: 获取指定检测器的指标
        - get_report: 获取性能报告
        - reset: 重置监控数据
        - track: 上下文管理器，自动记录执行时间
    
    Example:
        >>> monitor = PerformanceMonitor()
        >>> with monitor.track("OOMDetector"):
        ...     detector.detect(log, context)
    """
    
    def __init__(self) -> None:
        """初始化监控器。"""
        self._metrics: Dict[str, DetectorMetrics] = {}
        self._lock = threading.RLock()
        self._start_time = time.time()
        self._analysis_count = 0
    
    def record(
        self,
        detector_name: str,
        execution_time_ms: float,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """
        记录检测结果。
        
        Args:
            detector_name: 检测器名称
            execution_time_ms: 执行时间（毫秒）
            success: 是否成功
            error: 错误信息（如果有）
        """
        with self._lock:
            if detector_name not in self._metrics:
                self._metrics[detector_name] = DetectorMetrics(name=detector_name)
            
            metrics = self._metrics[detector_name]
            metrics.call_count += 1
            metrics.total_time_ms += execution_time_ms
            
            if execution_time_ms < metrics.min_time_ms:
                metrics.min_time_ms = execution_time_ms
            if execution_time_ms > metrics.max_time_ms:
                metrics.max_time_ms = execution_time_ms
            
            if success:
                metrics.success_count += 1
            else:
                metrics.error_count += 1
                metrics.last_error = error
                metrics.last_error_time = time.time()
    
    def increment_analysis(self) -> None:
        """增加分析计数。"""
        with self._lock:
            self._analysis_count += 1
    
    @contextmanager
    def track(self, detector_name: str) -> Generator[None, None, None]:
        """
        上下文管理器，自动记录执行时间。
        
        Args:
            detector_name: 检测器名称
            
        Yields:
            None
            
        Example:
            >>> with monitor.track("OOMDetector"):
            ...     result = detector.detect(log, context)
        """
        start_time = time.perf_counter()
        error_msg = None
        success = True
        
        try:
            yield
        except Exception as e:
            success = False
            error_msg = str(e)
            raise
        finally:
            end_time = time.perf_counter()
            execution_time_ms = (end_time - start_time) * 1000
            self.record(detector_name, execution_time_ms, success, error_msg)
    
    def get_metrics(self, detector_name: str) -> Optional[DetectorMetrics]:
        """
        获取指定检测器的指标。
        
        Args:
            detector_name: 检测器名称
            
        Returns:
            性能指标，如果不存在返回 None
        """
        return self._metrics.get(detector_name)
    
    def get_all_metrics(self) -> Dict[str, DetectorMetrics]:
        """获取所有检测器指标。"""
        return dict(self._metrics)
    
    def get_report(self) -> PerformanceReport:
        """
        获取性能报告。
        
        Returns:
            性能报告对象
        """
        with self._lock:
            return PerformanceReport(
                start_time=self._start_time,
                end_time=time.time(),
                total_analyses=self._analysis_count,
                total_detectors=len(self._metrics),
                metrics=dict(self._metrics),
            )
    
    def reset(self) -> None:
        """重置监控数据。"""
        with self._lock:
            self._metrics.clear()
            self._start_time = time.time()
            self._analysis_count = 0
    
    def log_summary(self, level: int = logging.INFO) -> None:
        """
        记录性能摘要日志。
        
        Args:
            level: 日志级别
        """
        report = self.get_report()
        
        logger.log(level, "=== 检测器性能报告 ===")
        logger.log(level, "总分析次数: %d", report.total_analyses)
        logger.log(level, "检测器数量: %d", report.total_detectors)
        
        slow = report.get_slow_detectors()
        if slow:
            logger.log(level, "慢检测器 (>1000ms): %s", [m.name for m in slow])
        
        errors = report.get_error_detectors()
        if errors:
            logger.log(level, "有错误的检测器: %s", [m.name for m in errors])
        
        for name, metrics in sorted(
            self._metrics.items(),
            key=lambda x: x[1].total_time_ms,
            reverse=True,
        )[:5]:
            logger.log(
                level,
                "  %s: %d 次调用, 平均 %.2fms, 成功率 %.1f%%",
                name,
                metrics.call_count,
                metrics.avg_time_ms,
                metrics.success_rate * 100,
            )


_global_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """
    获取全局性能监控器实例。
    
    Returns:
        PerformanceMonitor 实例
    """
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    return _global_monitor


def reset_performance_monitor() -> None:
    """重置全局性能监控器（仅用于测试）。"""
    global _global_monitor
    if _global_monitor is not None:
        _global_monitor.reset()
        _global_monitor = None
