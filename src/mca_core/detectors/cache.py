"""
检测器缓存模块

提供检测结果缓存，避免重复分析相同内容。

模块说明:
    本模块提供检测器结果缓存功能，支持：
        - LRU 缓存策略
        - TTL 过期机制
        - 内存使用限制
        - 缓存统计
    
    主要组件:
        - DetectorCache: 检测结果缓存类
        - CacheEntry: 缓存条目数据类
        - CacheStats: 缓存统计数据类
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from mca_core.detectors.contracts import DetectionResult

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """
    缓存条目。
    
    Attributes:
        key: 缓存键（日志内容的哈希）
        results: 检测结果列表
        created_at: 创建时间戳
        expires_at: 过期时间戳
        size_bytes: 估计大小（字节）
        hit_count: 命中次数
    """
    
    key: str
    results: List["DetectionResult"]
    created_at: float
    expires_at: float
    size_bytes: int = 0
    hit_count: int = 0
    
    def is_expired(self) -> bool:
        """检查是否已过期。"""
        return time.time() > self.expires_at


@dataclass
class CacheStats:
    """
    缓存统计数据。
    
    Attributes:
        hits: 缓存命中次数
        misses: 缓存未命中次数
        evictions: 缓存驱逐次数
        size: 当前条目数
        max_size: 最大条目数
        memory_bytes: 当前内存使用（字节）
        max_memory_bytes: 最大内存限制
    """
    
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0
    max_size: int = 1000
    memory_bytes: int = 0
    max_memory_bytes: int = 100 * 1024 * 1024
    
    @property
    def hit_rate(self) -> float:
        """计算缓存命中率。"""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "hit_rate": f"{self.hit_rate:.2%}",
            "size": self.size,
            "max_size": self.max_size,
            "memory_mb": self.memory_bytes / (1024 * 1024),
            "max_memory_mb": self.max_memory_bytes / (1024 * 1024),
        }


class DetectorCache:
    """
    检测结果缓存。
    
    使用 LRU 策略管理缓存，支持 TTL 过期和内存限制。
    
    Attributes:
        _max_size: 最大缓存条目数
        _max_memory_bytes: 最大内存使用（字节）
        _default_ttl: 默认过期时间（秒）
        _cache: 缓存存储（OrderedDict）
        _stats: 缓存统计
        _lock: 线程锁
    
    方法:
        - get: 获取缓存结果
        - set: 设置缓存结果
        - has: 检查缓存是否存在
        - delete: 删除缓存条目
        - clear: 清空缓存
        - get_stats: 获取缓存统计
        - cleanup: 清理过期条目
    
    Example:
        >>> cache = DetectorCache(max_size=1000, ttl_seconds=300)
        >>> cache.set(log_hash, results)
        >>> cached = cache.get(log_hash)
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        max_memory_mb: int = 100,
        ttl_seconds: float = 300.0,
    ) -> None:
        """
        初始化缓存。
        
        Args:
            max_size: 最大缓存条目数
            max_memory_mb: 最大内存使用（MB）
            ttl_seconds: 默认过期时间（秒）
        """
        self._max_size = max_size
        self._max_memory_bytes = max_memory_mb * 1024 * 1024
        self._default_ttl = ttl_seconds
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._stats = CacheStats(
            max_size=max_size,
            max_memory_bytes=self._max_memory_bytes,
        )
        self._lock = threading.RLock()
    
    @staticmethod
    def compute_key(crash_log: str) -> str:
        """
        计算缓存键。
        
        使用 SHA256 哈希日志内容。
        
        Args:
            crash_log: 崩溃日志文本
            
        Returns:
            缓存键字符串
        """
        return hashlib.sha256(crash_log.encode("utf-8", errors="replace")).hexdigest()[:32]
    
    def get(self, key: str) -> Optional[List["DetectionResult"]]:
        """
        获取缓存结果。
        
        如果缓存存在且未过期，返回结果并更新 LRU 顺序。
        
        Args:
            key: 缓存键
            
        Returns:
            检测结果列表，如果不存在或已过期返回 None
        """
        with self._lock:
            if key not in self._cache:
                self._stats.misses += 1
                return None
            
            entry = self._cache[key]
            
            if entry.is_expired():
                self._remove_entry(key)
                self._stats.misses += 1
                return None
            
            self._cache.move_to_end(key)
            entry.hit_count += 1
            self._stats.hits += 1
            
            return entry.results
    
    def set(
        self,
        key: str,
        results: List["DetectionResult"],
        ttl_seconds: Optional[float] = None,
    ) -> None:
        """
        设置缓存结果。
        
        如果缓存已满，会驱逐最旧的条目。
        
        Args:
            key: 缓存键
            results: 检测结果列表
            ttl_seconds: 过期时间（秒），None 使用默认值
        """
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        now = time.time()
        
        size_bytes = self._estimate_size(results)
        
        entry = CacheEntry(
            key=key,
            results=results,
            created_at=now,
            expires_at=now + ttl,
            size_bytes=size_bytes,
        )
        
        with self._lock:
            if key in self._cache:
                old_entry = self._cache[key]
                self._stats.memory_bytes -= old_entry.size_bytes
            
            self._cache[key] = entry
            self._cache.move_to_end(key)
            self._stats.memory_bytes += size_bytes
            self._stats.size = len(self._cache)
            
            self._evict_if_needed()
    
    def has(self, key: str) -> bool:
        """
        检查缓存是否存在且未过期。
        
        Args:
            key: 缓存键
            
        Returns:
            如果存在且有效返回 True
        """
        with self._lock:
            if key not in self._cache:
                return False
            
            entry = self._cache[key]
            if entry.is_expired():
                self._remove_entry(key)
                return False
            
            return True
    
    def delete(self, key: str) -> bool:
        """
        删除缓存条目。
        
        Args:
            key: 缓存键
            
        Returns:
            如果成功删除返回 True
        """
        with self._lock:
            if key in self._cache:
                self._remove_entry(key)
                return True
            return False
    
    def clear(self) -> None:
        """清空所有缓存。"""
        with self._lock:
            self._cache.clear()
            self._stats.memory_bytes = 0
            self._stats.size = 0
    
    def cleanup(self) -> int:
        """
        清理所有过期条目。
        
        Returns:
            清理的条目数
        """
        removed = 0
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                self._remove_entry(key)
                removed += 1
        
        return removed
    
    def get_stats(self) -> CacheStats:
        """
        获取缓存统计。
        
        Returns:
            缓存统计数据
        """
        with self._lock:
            self._stats.size = len(self._cache)
            return self._stats
    
    def _remove_entry(self, key: str) -> None:
        """移除缓存条目（内部方法）。"""
        if key in self._cache:
            entry = self._cache.pop(key)
            self._stats.memory_bytes -= entry.size_bytes
            self._stats.evictions += 1
            self._stats.size = len(self._cache)
    
    def _evict_if_needed(self) -> None:
        """如果需要则驱逐条目。"""
        while len(self._cache) > self._max_size:
            oldest_key = next(iter(self._cache))
            self._remove_entry(oldest_key)
        
        while self._stats.memory_bytes > self._max_memory_bytes and self._cache:
            oldest_key = next(iter(self._cache))
            self._remove_entry(oldest_key)
    
    def _estimate_size(self, results: List["DetectionResult"]) -> int:
        """估计结果大小。"""
        total = 0
        for r in results:
            total += len(r.detector) * 2
            total += len(r.message) * 2
            if r.cause_label:
                total += len(r.cause_label) * 2
            for key, value in r.metadata.items():
                total += len(key) * 2
                if isinstance(value, str):
                    total += len(value) * 2
        return total


_global_cache: Optional[DetectorCache] = None


def get_detector_cache() -> DetectorCache:
    """
    获取全局检测器缓存实例。
    
    Returns:
        DetectorCache 实例
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = DetectorCache()
    return _global_cache


def reset_detector_cache() -> None:
    """重置全局检测器缓存（仅用于测试）。"""
    global _global_cache
    if _global_cache is not None:
        _global_cache.clear()
        _global_cache = None
