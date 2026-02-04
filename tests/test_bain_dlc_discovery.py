from __future__ import annotations

import importlib.util
from pathlib import Path

from brain_system.discovery import load_dlc_classes_from_file


def test_bain_extra_dlcs_discoverable_or_skipped() -> None:
    dlc_file = Path(__file__).resolve().parents[1] / "dlcs" / "bain_extra_dlcs.py"
    assert dlc_file.exists(), "bain_extra_dlcs.py 应存在于 dlcs 目录以便自动发现"

    classes = load_dlc_classes_from_file(dlc_file)

    has_numpy = importlib.util.find_spec("numpy") is not None
    if not has_numpy:
        # 未安装 numpy 时，包装器应跳过导出，避免自动发现阶段刷屏报错。
        assert classes == []
        return

    names = {c.__name__ for c in classes}
    assert "HardwareAcceleratorDLC" in names
    assert "NeuralNetworkOperatorsDLC" in names
    assert "NeuralWorkflowDLC" in names
    assert "DistributedComputingDLC" in names
