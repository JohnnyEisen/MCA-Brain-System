from pathlib import Path

from mca_core.security import InputSanitizer


def test_validate_file_path_allows_file_inside_base(tmp_path: Path) -> None:
    base = tmp_path / "safe"
    base.mkdir()
    target = base / "a.log"
    target.write_text("ok", encoding="utf-8")

    assert InputSanitizer.validate_file_path(str(target), base_dir=str(base))


def test_validate_file_path_blocks_prefix_traversal_bypass(tmp_path: Path) -> None:
    base = tmp_path / "safe"
    base.mkdir()

    attacker_dir = tmp_path / "safe_evil"
    attacker_dir.mkdir()
    attacker_file = attacker_dir / "steal.log"
    attacker_file.write_text("pwnd", encoding="utf-8")

    assert not InputSanitizer.validate_file_path(str(attacker_file), base_dir=str(base))


def test_validate_dir_path_blocks_prefix_traversal_bypass(tmp_path: Path) -> None:
    base = tmp_path / "safe"
    base.mkdir()

    attacker_dir = tmp_path / "safe_evil"
    attacker_dir.mkdir()

    assert not InputSanitizer.validate_dir_path(str(attacker_dir), base_dir=str(base))


def test_validate_dir_path_create_mode_allows_parent_inside_base(tmp_path: Path) -> None:
    base = tmp_path / "safe"
    base.mkdir()
    (base / "new").mkdir()

    new_dir = base / "new" / "child"
    assert InputSanitizer.validate_dir_path(str(new_dir), base_dir=str(base), create=True)


def test_validate_path_rejects_null_byte() -> None:
    assert not InputSanitizer.validate_file_path("bad\x00path")
    assert not InputSanitizer.validate_dir_path("bad\x00path")
