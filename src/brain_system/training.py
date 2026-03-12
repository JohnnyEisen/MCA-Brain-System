from __future__ import annotations

import asyncio
import os
import random
import statistics
import tempfile
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional
from config.constants import LAB_SAMPLE_SIZE


@dataclass(slots=True)
class TrainingConfig:
    duration_seconds: float = 20.0
    concurrency: int = 20
    cpu_task_size: int = 32
    io_bytes: int = LAB_SAMPLE_SIZE
    include_io: bool = True
    include_cpu: bool = True
    include_cache_warmup: bool = True


@dataclass(slots=True)
class TrainingReport:
    started_at: float
    ended_at: float
    total_tasks: int
    successes: int
    failures: int
    latencies_ms_p50: float
    latencies_ms_p95: float
    recommended_config: dict[str, Any]


ProgressCallback = Callable[[str], None]


def _now() -> float:
    return time.time()


def _fibonacci(n: int) -> int:
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


def _hash_work(data: bytes, rounds: int = 200) -> str:
    import hashlib

    h = hashlib.sha256(data).digest()
    for _ in range(rounds):
        h = hashlib.sha256(h).digest()
    return h.hex()


def _io_work(nbytes: int) -> int:
    # 纯本地临时文件 I/O
    b = os.urandom(nbytes)
    with tempfile.NamedTemporaryFile(delete=True) as f:
        f.write(b)
        f.flush()
        f.seek(0)
        r = f.read()
    return len(r)


class BrainTrainer:
    """训练入口（非 ML 训练）：通过压测/基准 + 缓存预热来提升实际吞吐，并输出配置建议。

    说明：
    - 这里的“训练”指对 BrainCore 运行态做 workload 训练（warmup + profiling + tuning suggestion），
      不是训练神经网络模型。
    - 生产上常见做法是用这类训练自动给出 thread/process pool、cache TTL 等参数建议。
    """

    async def train(
        self,
        brain: Any,
        *,
        cfg: TrainingConfig,
        progress: Optional[ProgressCallback] = None,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> TrainingReport:
        progress = progress or (lambda _: None)
        cancel_event = cancel_event or asyncio.Event()

        started = _now()
        deadline = started + float(cfg.duration_seconds)

        progress("训练开始：压测与预热中...")

        latencies: list[float] = []
        successes = 0
        failures = 0
        total = 0

        async def one_job(job_id: int) -> None:
            nonlocal successes, failures, total
            if cancel_event.is_set():
                return

            # 随机混合 workload
            r = random.random()
            task_id = f"train_{job_id}"

            t0 = _now()
            try:
                if cfg.include_cpu and r < 0.5:
                    # 用 cpu_ 前缀触发进程池策略（如果启用）
                    await brain.compute(f"cpu_train_{job_id}", _fibonacci, int(cfg.cpu_task_size))
                elif cfg.include_io and r < 0.8:
                    await brain.compute(f"io_train_{job_id}", _io_work, int(cfg.io_bytes))
                else:
                    data = os.urandom(256)
                    await brain.compute(task_id, _hash_work, data)

                successes += 1
            except Exception:
                failures += 1
            finally:
                total += 1
                latencies.append((_now() - t0) * 1000.0)

        # 可选：缓存预热（让 result_cache/磁盘 cache 更快进入稳定态）
        if cfg.include_cache_warmup:
            progress("缓存预热：执行一组固定任务...")
            try:
                await brain.compute("warmup_hash", _hash_work, b"warmup")
                await brain.compute("warmup_fib", _fibonacci, 28)
            except Exception:
                pass

        # 并发压测循环
        while _now() < deadline and not cancel_event.is_set():
            batch = []
            for i in range(int(cfg.concurrency)):
                batch.append(asyncio.create_task(one_job(total + i)))
            await asyncio.gather(*batch, return_exceptions=True)
            progress(f"训练中：total={total} ok={successes} fail={failures}")

        ended = _now()

        p50 = statistics.quantiles(latencies, n=100)[49] if len(latencies) >= 100 else (statistics.median(latencies) if latencies else 0.0)
        p95 = statistics.quantiles(latencies, n=100)[94] if len(latencies) >= 100 else (max(latencies) if latencies else 0.0)

        recommended = self.recommend_config(brain, cfg=cfg, latencies_ms=latencies)
        progress("训练完成：已生成配置建议。")

        return TrainingReport(
            started_at=started,
            ended_at=ended,
            total_tasks=total,
            successes=successes,
            failures=failures,
            latencies_ms_p50=float(p50),
            latencies_ms_p95=float(p95),
            recommended_config=recommended,
        )

    def recommend_config(self, brain: Any, *, cfg: TrainingConfig, latencies_ms: list[float]) -> dict[str, Any]:
        """给出可落地的配置建议（不直接热改 thread/process pool，因为那涉及重建 executor）。"""

        out: dict[str, Any] = {}

        # cache 建议：根据访问量/淘汰率估算目标值，避免每次简单翻倍
        cache = getattr(brain, "result_cache", None)
        if cache is not None:
            hits = int(getattr(cache, "hits", 0))
            misses = int(getattr(cache, "misses", 0))
            evictions = int(getattr(cache, "evictions", 0))
            total_access = hits + misses

            # 访问量不足时不做激进建议
            if total_access >= 100 and evictions > 0:
                pressure = evictions / max(1, total_access)

                if pressure < 0.01:
                    factor = 1.1
                elif pressure < 0.05:
                    factor = 1.5
                elif pressure < 0.1:
                    factor = 2.0
                else:
                    factor = 3.0

                current = int(getattr(cache, "max_entries", 10_000))
                cap = int(brain.config.get("cache_max_entries_cap", 200_000))
                target = int(current * factor)

                out["cache_max_entries"] = max(min(target, cap), 10_000)

        # retry 建议：如果失败较多，建议提高重试次数（上限保护）
        if latencies_ms:
            p95 = statistics.quantiles(latencies_ms, n=100)[94] if len(latencies_ms) >= 100 else max(latencies_ms)
            if p95 > 1500:
                out["retry_max_attempts"] = min(int(brain.config.get("retry_max_attempts", 1)) + 1, 5)

        # 训练面板建议项
        out["ui_refresh_ms"] = int(brain.config.get("ui_refresh_ms", 1000))

        # 建议保留当前 dlc 签名策略
        out["dlc_signature_required"] = bool(brain.config.get("dlc_signature_required", False))

        return out
