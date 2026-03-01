"""异步重试机制模块。

提供可配置的重试策略和异步重试装饰器。
"""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass(slots=True)
class RetryPolicy:
    """重试策略配置。

    Attributes:
        max_attempts: 最大尝试次数。
        initial_delay_seconds: 初始延迟时间（秒）。
        max_delay_seconds: 最大延迟时间（秒）。
        backoff_multiplier: 退避乘数。
        jitter_ratio: 抖动比例（0-1）。
    """

    max_attempts: int = 3
    initial_delay_seconds: float = 0.2
    max_delay_seconds: float = 5.0
    backoff_multiplier: float = 2.0
    jitter_ratio: float = 0.2


# 默认可重试的异常类型
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
    """异步重试执行函数。

    Args:
        func: 要执行的异步函数。
        policy: 重试策略。
        should_retry: 判断是否重试的函数，默认使用 is_retriable_exception。

    Returns:
        函数执行结果。

    Raises:
        ValueError: max_attempts 不合法。
        BaseException: 重试次数耗尽后抛出最后一次异常。
    """
    if policy.max_attempts <= 0:
        raise ValueError("max_attempts must be > 0")

    attempt = 1
    delay = float(policy.initial_delay_seconds)

    while True:
        try:
            return await func()
        except BaseException as exc:
            predicate = should_retry or is_retriable_exception
            if attempt >= policy.max_attempts or not predicate(exc):
                raise

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
