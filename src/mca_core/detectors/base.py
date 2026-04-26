"""
检测器基类模块

定义统一的检测器接口，支持优先级排序和置信度评估。

类说明:
    - Detector: 检测器抽象基类，所有检测器必须继承此类
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Optional

from .contracts import AnalysisContext, DetectionResult

if TYPE_CHECKING:
    pass


class Detector(ABC):
    """
    统一的检测器抽象基类。
    
    所有崩溃日志检测器必须继承此类并实现其抽象方法。
    检测器支持优先级排序，优先级较低的检测器会先执行。
    
    类属性:
        PRIORITY_CRITICAL: 关键优先级 (0)，最先执行
        PRIORITY_HIGH: 高优先级 (10)
        PRIORITY_NORMAL: 普通优先级 (50)，默认值
        PRIORITY_LOW: 低优先级 (100)，最后执行
    
    方法:
        - detect: 执行检测逻辑（抽象方法）
        - get_name: 获取检测器名称（抽象方法）
        - get_cause_label: 获取关联的原因标签（抽象方法）
        - get_priority: 获取检测优先级
        - get_confidence: 获取默认置信度
    """

    PRIORITY_CRITICAL: int = 0
    PRIORITY_HIGH: int = 10
    PRIORITY_NORMAL: int = 50
    PRIORITY_LOW: int = 100

    @abstractmethod
    def detect(
        self,
        crash_log: str,
        context: AnalysisContext
    ) -> List[DetectionResult]:
        """
        对崩溃日志执行检测。
        
        Args:
            crash_log: 崩溃日志文本
            context: 分析上下文，用于存储结果
            
        Returns:
            检测结果列表
            
        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError

    @abstractmethod
    def get_name(self) -> str:
        """
        获取检测器的人类可读名称。
        
        Returns:
            检测器名称字符串
            
        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError

    @abstractmethod
    def get_cause_label(self) -> Optional[str]:
        """
        获取与此检测器关联的原因标签。
        
        用于在摘要中统计崩溃原因。
        
        Returns:
            原因标签字符串，如果没有关联标签则返回 None
            
        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError

    def get_priority(self) -> int:
        """
        获取检测优先级。
        
        较低的值会先执行。默认返回 PRIORITY_NORMAL。
        
        Returns:
            优先级整数值
        """
        return self.PRIORITY_NORMAL

    def get_confidence(self) -> float:
        """
        获取此检测器结果的默认置信度。
        
        Returns:
            置信度值，范围 0.0-1.0
        """
        return 0.8
