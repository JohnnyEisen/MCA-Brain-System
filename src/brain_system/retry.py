"""异步重试机制模块。

提供可配置的重试策略、异步重试装饰器和断路器模式。
"""
from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable
import logging


class CircuitState(Enum):
    """断路器状态。"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(slots=True)
class CircuitBreaker:
    """断路器实现。
    
    防止级联故障，当失败率达到阈值时快速失败。
    
    Attributes:
        failure_threshold: 触发断路的失败次数阈值。
        recovery_timeout: 断路后恢复尝试的超时时间（秒）。
        success_threshold: 半开状态下恢复关闭状态的成功次数阈值。
    """
    
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    success_threshold: int = 2
    
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failures: int = field(default=0, init=False)
    _successes: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    
    @property
    def state(self) -> CircuitState:
        """当前断路器状态。"""
        return self._state
    
    @property
    def is_closed(self) -> bool:
        """断路器是否关闭（正常）。"""
        return self._state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        """断路器是否打开（熔断）。"""
        return self._state == CircuitState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        """断路器是否半开（恢复尝试）。"""
        return self._state == CircuitState.HALF_OPEN
    
    async def can_execute(self) -> bool:
        """检查是否允许执行。
        
        Returns:
            是否允许执行请求。
        """
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            
            if self._state == CircuitState.OPEN:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._successes = 0
                    logging.info("Circuit breaker entering HALF_OPEN state")
                    return True
                return False
            
            # HALF_OPEN: 允许有限请求通过
            return True
    
    async def record_success(self) -> None:
        """记录成功调用。"""
        async with self._lock:
            self._failures = 0
            
            if self._state == CircuitState.HALF_OPEN:
                self._successes += 1
                if self._successes >= self.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._successes = 0
                    logging.info("Circuit breaker recovered to CLOSED state")
    
    async def record_failure(self) -> None:
        """记录失败调用。"""
        async with self._lock:
            self._failures += 1
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logging.warning("Circuit breaker reopened from HALF_OPEN state")
            elif self._failures >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logging.warning(
                    "Circuit breaker opened after %d failures (threshold: %d)",
                    self._failures, self.failure_threshold
                )
    
    def get_stats(self) -> dict:
        """获取断路器统计信息。"""
        return {
            "state": self._state.value,
            "failures": self._failures,
            "successes": self._successes,
            "last_failure_time": self._last_failure_time,
        }


class CircuitBreakerOpenError(Exception):
    """断路器打开时抛出的异常。"""
    pass


@dataclass(slots=True)
class RetryPolicy:
    """重试策略配置。

    Attributes:
        max_attempts: 最大尝试次数。
        initial_delay_seconds: 初始延迟时间（秒）。
        max_delay_seconds: 最大延迟时间（秒）。
        backoff_multiplier: 退避乘数。
        jitter_ratio: 抖动比例（0-1）。
        timeout_seconds: 单次执行超时时间（秒），0 表示无限制。
        circuit_breaker: 可选的断路器实例。
    """

    max_attempts: int = 3
    initial_delay_seconds: float = 0.2
    max_delay_seconds: float = 5.0
    backoff_multiplier: float = 2.0
    jitter_ratio: float = 0.2
    timeout_seconds: float = 0.0
    circuit_breaker: CircuitBreaker | None = None


_DEFAULT_RETRIABLE: tuple[type[BaseException], ...] = (
    TimeoutError,
    ConnectionError,
    OSError,
)


def is_retriable_exception(exc: BaseException) -> bool:
    """检查异常是否可重试。

    Args:
        exc: 要检查的异常。

    Returns:
        是否可重试。
    """
    return isinstance(exc, _DEFAULT_RETRIABLE)


async def async_retry(
    func: Callable[[], Awaitable[object]],
    *,
    policy: RetryPolicy,
    should_retry: Callable[[BaseException], bool] | None = None,
) -> object:
    """异步重试执行函数，支持断路器和超时。

    Args:
        func: 要执行的异步函数。
        policy: 重试策略。
        should_retry: 判断是否重试的函数，默认使用 is_retriable_exception。

    Returns:
        函数执行结果。

    Raises:
        ValueError: max_attempts 不合法。
        CircuitBreakerOpenError: 断路器打开时。
        TimeoutError: 执行超时。
        BaseException: 重试次数耗尽后抛出最后一次异常。
    """
    if policy.max_attempts <= 0:
        raise ValueError("max_attempts must be > 0")

    attempt = 1
    delay = float(policy.initial_delay_seconds)
    cb = policy.circuit_breaker

    while True:
        # 断路器检查
        if cb is not None and not await cb.can_execute():
            raise CircuitBreakerOpenError(
                f"Circuit breaker is open, rejecting request"
            )
        
        try:
            # 支持超时
            if policy.timeout_seconds > 0:
                result = await asyncio.wait_for(
                    func(), timeout=policy.timeout_seconds
                )
            else:
                result = await func()
            
            # 成功时更新断路器
            if cb is not None:
                await cb.record_success()
            
            return result
            
        except asyncio.TimeoutError as exc:
            if cb is not None:
                await cb.record_failure()
            if attempt >= policy.max_attempts:
                raise TimeoutError(
                    f"Task timed out after {policy.timeout_seconds}s"
                ) from exc
            
        except BaseException as exc:
            if cb is not None:
                await cb.record_failure()
            
            predicate = should_retry or is_retriable_exception
            if attempt >= policy.max_attempts or not predicate(exc):
                raise

        # 计算延迟并等待
        jitter = delay * float(policy.jitter_ratio)
        sleep_for = max(
            0.0,
            min(
                float(policy.max_delay_seconds),
                delay + random.uniform(-jitter, jitter),
            ),
        )
        await asyncio.sleep(sleep_for)

        attempt += 1
        delay = min(
            float(policy.max_delay_seconds),
            delay * float(policy.backoff_multiplier),
        )


class RetryBudget:
    """全局重试预算管理器。
    
    限制系统范围内的重试次数，防止重试风暴。
    """
    
    def __init__(self, max_retries_per_second: float = 100.0):
        self._max_retries_per_second = max_retries_per_second
        self._retry_times: list[float] = []
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> bool:
        """尝试获取重试预算。
        
        Returns:
            是否允许重试。
        """
        async with self._lock:
            now = time.time()
            # 清理超过1秒的记录
            self._retry_times = [t for t in self._retry_times if now - t < 1.0]
            
            if len(self._retry_times) >= self._max_retries_per_second:
                return False
            
            self._retry_times.append(now)
            return True
    
    def get_current_rate(self) -> float:
        """获取当前重试速率（次/秒）。"""
        now = time.time()
        recent = [t for t in self._retry_times if now - t < 1.0]
        return float(len(recent))
