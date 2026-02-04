import pytest

from brain_system.retry import RetryPolicy, async_retry


@pytest.mark.asyncio
async def test_async_retry_succeeds_after_failures():
    attempts = {"n": 0}

    async def fn():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise TimeoutError("x")
        return 42

    r = await async_retry(fn, policy=RetryPolicy(max_attempts=5, initial_delay_seconds=0.0))
    assert r == 42
