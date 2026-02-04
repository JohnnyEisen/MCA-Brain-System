from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, Type


@dataclass(slots=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_delay_seconds: float = 0.2
    max_delay_seconds: float = 5.0
    backoff_multiplier: float = 2.0
    jitter_ratio: float = 0.2


_DEFAULT_RETRIABLE: tuple[Type[BaseException], ...] = (
    TimeoutError,
    ConnectionError,
    OSError,
)


def is_retriable_exception(exc: BaseException) -> bool:
    return isinstance(exc, _DEFAULT_RETRIABLE)


async def async_retry(
    func: Callable[[], Awaitable[object]],
    *,
    policy: RetryPolicy,
    should_retry: Optional[Callable[[BaseException], bool]] = None,
) -> object:
    if policy.max_attempts <= 0:
        raise ValueError("max_attempts must be > 0")

    attempt = 1
    delay = float(policy.initial_delay_seconds)

    while True:
        try:
            return await func()
        except BaseException as exc:  # noqa: BLE001
            predicate = should_retry or is_retriable_exception
            if attempt >= policy.max_attempts or not predicate(exc):
                raise

            jitter = delay * float(policy.jitter_ratio)
            sleep_for = max(0.0, min(float(policy.max_delay_seconds), delay + random.uniform(-jitter, jitter)))
            await asyncio.sleep(sleep_for)

            attempt += 1
            delay = min(float(policy.max_delay_seconds), delay * float(policy.backoff_multiplier))
