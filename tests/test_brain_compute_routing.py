import json
from pathlib import Path

from brain_system.core import BrainCore


def _make_brain(tmp_path: Path, override: dict) -> BrainCore:
    config = {
        "enable_disk_cache": False,
        "thread_pool_size": 2,
        "process_pool_size": 1,
        "executor_routing_strategy": "balanced",
    }
    config.update(override)
    config_file = tmp_path / "brain_config.json"
    config_file.write_text(json.dumps(config), encoding="utf-8")
    return BrainCore(config_path=str(config_file))


def _shutdown_brain(brain: BrainCore) -> None:
    if brain.thread_pool:
        brain.thread_pool.shutdown(wait=True)
    if brain.process_pool:
        brain.process_pool.shutdown(wait=True)


def test_balanced_strategy_routes_cpu_hint_to_process(tmp_path: Path) -> None:
    brain = _make_brain(tmp_path, {"executor_routing_strategy": "balanced"})
    try:
        kind = brain._select_executor_kind(task_id="cpu_task_1", priority=0, args=(1,), kwargs={})
        assert kind == "process"
    finally:
        _shutdown_brain(brain)


def test_high_priority_routes_to_thread_for_latency(tmp_path: Path) -> None:
    brain = _make_brain(tmp_path, {"executor_routing_strategy": "throughput"})
    try:
        kind = brain._select_executor_kind(task_id="cpu_task_1", priority=2, args=(1,), kwargs={})
        assert kind == "thread"
    finally:
        _shutdown_brain(brain)


def test_large_payload_falls_back_to_thread(tmp_path: Path) -> None:
    brain = _make_brain(
        tmp_path,
        {
            "executor_routing_strategy": "throughput",
            "process_pool_payload_max_bytes": 1024,
        },
    )
    try:
        large_arg = "x" * 10_000
        kind = brain._select_executor_kind(task_id="cpu_task_1", priority=0, args=(large_arg,), kwargs={})
        assert kind == "thread"
    finally:
        _shutdown_brain(brain)


def test_latency_strategy_prefers_thread(tmp_path: Path) -> None:
    brain = _make_brain(tmp_path, {"executor_routing_strategy": "latency"})
    try:
        kind = brain._select_executor_kind(task_id="cpu_task_1", priority=0, args=(1,), kwargs={})
        assert kind == "thread"
    finally:
        _shutdown_brain(brain)
