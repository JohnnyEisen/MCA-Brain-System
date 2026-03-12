from pathlib import Path

from brain_system.core import BrainCore


def test_signature_required_rejects_without_public_keys(tmp_path: Path):
    dlcs = tmp_path / "dlcs"
    dlcs.mkdir()

    dlc_file = dlcs / "x.py"
    dlc_file.write_text("class X: pass\n", encoding="utf-8")

    # 不提供公钥，且强制签名 => 必须拒绝加载（在 import/exec 之前就失败）
    brain = BrainCore(config_path=None)
    brain.config["dlc_signature_required"] = True
    brain.config["dlc_public_key_pem_files"] = []

    loaded = brain.load_dlc_file(str(dlc_file))
    assert loaded == 0
