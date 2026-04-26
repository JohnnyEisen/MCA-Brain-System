import json
import multiprocessing
from pathlib import Path

from brain_system.config_validator import build_config, load_config_file, validate_config


def test_build_config_defaults_match_core_runtime_behavior() -> None:
    config = build_config(None)
    cpu_count = multiprocessing.cpu_count()

    if cpu_count <= 8:
        assert config["executor_autotune_resolved_profile"] == "small_core"
        assert config["thread_pool_size"] == min(max(cpu_count * 2, 4), 16)
        assert config["process_pool_size"] == max(0, min(cpu_count // 2, 4))
        assert config["executor_routing_strategy"] == "latency"
        assert config["process_pool_payload_max_bytes"] == 131072
    else:
        assert config["executor_autotune_resolved_profile"] == "large_core"
        assert config["thread_pool_size"] == min(cpu_count * 4, 64)
        assert config["process_pool_size"] == min(cpu_count, 16)
        assert config["executor_routing_strategy"] == "throughput"
        assert config["process_pool_payload_max_bytes"] == 524288

    assert config["config_source"] == "file"
    assert config["executor_autotune_profile"] == "auto"


def test_build_config_merges_file_override(tmp_path: Path) -> None:
    config_path = tmp_path / "brain_config.json"
    config_path.write_text(
        json.dumps({"log_level": "DEBUG", "cache_max_entries": 256}),
        encoding="utf-8",
    )

    config = build_config(str(config_path))

    assert config["log_level"] == "DEBUG"
    assert config["cache_max_entries"] == 256


def test_build_config_manual_profile_keeps_manual_values(tmp_path: Path) -> None:
    config_path = tmp_path / "manual_profile.json"
    config_path.write_text(
        json.dumps(
            {
                "executor_autotune_profile": "manual",
                "thread_pool_size": 42,
                "process_pool_size": 3,
                "executor_routing_strategy": "balanced",
                "process_pool_payload_max_bytes": 204800,
            }
        ),
        encoding="utf-8",
    )

    config = build_config(str(config_path))

    assert config["executor_autotune_resolved_profile"] == "manual"
    assert config["thread_pool_size"] == 42
    assert config["process_pool_size"] == 3
    assert config["executor_routing_strategy"] == "balanced"
    assert config["process_pool_payload_max_bytes"] == 204800


def test_build_config_explicit_small_core_profile_uses_profile_keys(tmp_path: Path) -> None:
    config_path = tmp_path / "small_core_profile.json"
    config_path.write_text(
        json.dumps(
            {
                "executor_autotune_profile": "small_core",
                "thread_pool_size_small_core": 10,
                "process_pool_size_small_core": 2,
                "executor_routing_strategy_small_core": "latency",
                "process_pool_payload_max_bytes_small_core": 65536,
            }
        ),
        encoding="utf-8",
    )

    config = build_config(str(config_path))

    assert config["executor_autotune_resolved_profile"] == "small_core"
    assert config["thread_pool_size"] == 10
    assert config["process_pool_size"] == 2
    assert config["executor_routing_strategy"] == "latency"
    assert config["process_pool_payload_max_bytes"] == 65536


def test_load_config_file_rejects_non_dict_root(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid_root.json"
    config_path.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")

    assert load_config_file(str(config_path)) == {}


def test_validate_config_reports_invalid_values() -> None:
    errors = validate_config(
        {
            "thread_pool_size": 0,
            "log_level": "TRACE",
            "executor_routing_strategy": "unknown",
            "executor_autotune_profile": "ultra",
        }
    )

    assert any("thread_pool_size" in err for err in errors)
    assert any("log_level" in err for err in errors)
    assert any("executor_routing_strategy" in err for err in errors)
    assert any("executor_autotune_profile" in err for err in errors)
