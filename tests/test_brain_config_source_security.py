import json
from pathlib import Path

from brain_system.config import FileConfigSource


def test_file_config_source_rejects_oversized_file(tmp_path: Path) -> None:
    config_file = tmp_path / "too_large.json"
    config_file.write_text("x" * (1024 * 1024 + 1), encoding="utf-8")

    src = FileConfigSource(str(config_file))
    assert src.load() == {}


def test_file_config_source_rejects_non_dict_root(tmp_path: Path) -> None:
    config_file = tmp_path / "not_dict.json"
    config_file.write_text(json.dumps(["a", "b"]), encoding="utf-8")

    src = FileConfigSource(str(config_file))
    assert src.load() == {}


def test_file_config_source_accepts_dict_root(tmp_path: Path) -> None:
    config_file = tmp_path / "ok.json"
    config_file.write_text(json.dumps({"log_level": "INFO"}), encoding="utf-8")

    src = FileConfigSource(str(config_file))
    assert src.load() == {"log_level": "INFO"}
