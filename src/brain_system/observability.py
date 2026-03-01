"""可观测性模块。

提供 Prometheus 指标和 OpenTelemetry 追踪支持。
"""
from __future__ import annotations

from dataclasses import dataclass
from types import TracebackType
from typing import Any


@dataclass(slots=True)
class Observability:
    """可观测性配置。

    Attributes:
        enabled: 是否启用任何可观测性功能。
        metrics_enabled: 是否启用 Prometheus 指标。
        tracing_enabled: 是否启用追踪。
        task_seconds: 任务执行时间直方图。
        task_errors: 任务错误计数器。
        cache_hits: 缓存命中计数器。
        cache_misses: 缓存未命中计数器。
        dlc_loaded: DLC 加载计数器。
        tracer: OpenTelemetry 追踪器。
    """

    enabled: bool
    metrics_enabled: bool
    tracing_enabled: bool

    task_seconds: Any = None
    task_errors: Any = None
    cache_hits: Any = None
    cache_misses: Any = None
    dlc_loaded: Any = None

    tracer: Any = None


def build_observability(config: dict[str, Any]) -> Observability:
    """构建可观测性实例。

    Args:
        config: 配置字典，支持 enable_metrics 和 enable_tracing 选项。

    Returns:
        配置好的 Observability 实例。
    """
    metrics = bool(config.get("enable_metrics", False))
    tracing = bool(config.get("enable_tracing", False))
    enabled = metrics or tracing

    obs = Observability(
        enabled=enabled, metrics_enabled=metrics, tracing_enabled=tracing
    )

    if metrics:
        try:
            from prometheus_client import Counter, Histogram

            obs.task_seconds = Histogram(
                "brain_task_seconds",
                "Task execution latency in seconds",
                labelnames=("task_id",),
            )
            obs.task_errors = Counter(
                "brain_task_errors_total",
                "Total task failures",
                labelnames=("task_id",),
            )
            obs.cache_hits = Counter("brain_cache_hits_total", "Cache hits")
            obs.cache_misses = Counter("brain_cache_misses_total", "Cache misses")
            obs.dlc_loaded = Counter("brain_dlc_loaded_total", "Loaded DLC classes")
        except Exception:
            obs.metrics_enabled = False

    if tracing:
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter

            provider = TracerProvider(
                resource=Resource.create(
                    {"service.name": config.get("service_name", "brain")}
                )
            )
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
            trace.set_tracer_provider(provider)
            obs.tracer = trace.get_tracer(__name__)
        except Exception:
            obs.tracing_enabled = False

    obs.enabled = obs.metrics_enabled or obs.tracing_enabled
    return obs


class NullSpan:
    """空 Span，用于追踪未启用时的占位。"""

    def __enter__(self) -> NullSpan:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        return False


def start_span(obs: Observability, name: str) -> NullSpan:
    """启动一个追踪 Span。

    Args:
        obs: 可观测性实例。
        name: Span 名称。

    Returns:
        Span 上下文管理器。
    """
    if obs.tracing_enabled and obs.tracer is not None:
        try:
            return obs.tracer.start_as_current_span(name)
        except Exception:
            return NullSpan()
    return NullSpan()
