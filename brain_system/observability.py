from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(slots=True)
class Observability:
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
    metrics = bool(config.get("enable_metrics", False))
    tracing = bool(config.get("enable_tracing", False))
    enabled = metrics or tracing

    obs = Observability(enabled=enabled, metrics_enabled=metrics, tracing_enabled=tracing)

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

            provider = TracerProvider(resource=Resource.create({"service.name": config.get("service_name", "brain")}))
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
            trace.set_tracer_provider(provider)
            obs.tracer = trace.get_tracer(__name__)
        except Exception:
            obs.tracing_enabled = False

    obs.enabled = obs.metrics_enabled or obs.tracing_enabled
    return obs


class NullSpan:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def start_span(obs: Observability, name: str):
    if obs.tracing_enabled and obs.tracer is not None:
        try:
            return obs.tracer.start_as_current_span(name)
        except Exception:
            return NullSpan()
    return NullSpan()
