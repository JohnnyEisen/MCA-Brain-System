"""
mHC 训练配置文件

提供默认配置和命令行参数解析。

参考: UDMA 论文 - Xie et al., arXiv:2512.24880v2
"""
from __future__ import annotations

import json
import argparse
from dataclasses import dataclass, asdict, field
from typing import Optional, List
from pathlib import Path


@dataclass
class MHCConfig:
    """mHC 训练配置。"""

    enable_mhc: bool = True
    projection_interval: int = 500
    sinkhorn_iterations: int = 5
    sinkhorn_temperature: float = 0.1
    residual_scale: float = 0.1
    entropy_regularization: float = 0.01

    warmup_steps: int = 1000
    total_steps: int = 10000

    gradient_clip_norm: float = 1.0
    gradient_accumulation_steps: int = 1

    mhc_lr_ratio: float = 0.1
    mhc_weight_decay: float = 0.01


@dataclass
class ModelConfig:
    """模型配置。"""

    base_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    enable_mhc: bool = True
    mhc_residual_scale: float = 0.1
    mhc_hidden_ratio: float = 1.5
    sinkhorn_iterations: int = 5
    sinkhorn_temperature: float = 0.1
    projection_interval: int = 500
    num_mhc_blocks: int = 2
    mhc_dropout: float = 0.1
    trainable: bool = False
    fine_tune_base: bool = False


@dataclass
class TrainingConfig:
    """完整训练配置。"""

    model: ModelConfig = field(default_factory=ModelConfig)
    mhc: MHCConfig = field(default_factory=MHCConfig)

    batch_size: int = 8
    num_epochs: int = 3
    base_lr: float = 1e-4

    output_dir: str = "./mhc_checkpoints"
    log_interval: int = 100
    save_interval: int = 1000

    device: str = "cuda"
    seed: int = 42

    @classmethod
    def from_dict(cls, data: dict) -> "TrainingConfig":
        """从字典创建配置。"""
        if "model" in data:
            data["model"] = ModelConfig(**data["model"])
        if "mhc" in data:
            data["mhc"] = MHCConfig(**data["mhc"])
        return cls(**data)

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "model": asdict(self.model),
            "mhc": asdict(self.mhc),
            "batch_size": self.batch_size,
            "num_epochs": self.num_epochs,
            "base_lr": self.base_lr,
            "output_dir": self.output_dir,
            "log_interval": self.log_interval,
            "save_interval": self.save_interval,
            "device": self.device,
            "seed": self.seed,
        }

    def save(self, path: str) -> None:
        """保存配置到文件。"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> "TrainingConfig":
        """从文件加载配置。"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


def parse_args() -> TrainingConfig:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="mHC 训练配置",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--config", type=str, default=None,
        help="配置文件路径"
    )

    parser.add_argument(
        "--base-model", type=str,
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="基础模型名称"
    )

    parser.add_argument(
        "--enable-mhc", action="store_true", default=True,
        help="启用 mHC"
    )

    parser.add_argument(
        "--no-mhc", action="store_true",
        help="禁用 mHC"
    )

    parser.add_argument(
        "--projection-interval", type=int, default=500,
        help="投影更新间隔"
    )

    parser.add_argument(
        "--sinkhorn-iterations", type=int, default=5,
        help="Sinkhorn 迭代次数"
    )

    parser.add_argument(
        "--residual-scale", type=float, default=0.1,
        help="残差缩放因子"
    )

    parser.add_argument(
        "--batch-size", type=int, default=8,
        help="批次大小"
    )

    parser.add_argument(
        "--num-epochs", type=int, default=3,
        help="训练轮数"
    )

    parser.add_argument(
        "--base-lr", type=float, default=1e-4,
        help="基础学习率"
    )

    parser.add_argument(
        "--output-dir", type=str, default="./mhc_checkpoints",
        help="输出目录"
    )

    parser.add_argument(
        "--device", type=str, default="cuda",
        choices=["cuda", "cpu"],
        help="训练设备"
    )

    parser.add_argument(
        "--seed", type=int, default=42,
        help="随机种子"
    )

    args = parser.parse_args()

    if args.config:
        config = TrainingConfig.load(args.config)
    else:
        model_config = ModelConfig(
            base_model=args.base_model,
            enable_mhc=not args.no_mhc,
            projection_interval=args.projection_interval,
            sinkhorn_iterations=args.sinkhorn_iterations,
            mhc_residual_scale=args.residual_scale,
        )

        mhc_config = MHCConfig(
            projection_interval=args.projection_interval,
            sinkhorn_iterations=args.sinkhorn_iterations,
            residual_scale=args.residual_scale,
        )

        config = TrainingConfig(
            model=model_config,
            mhc=mhc_config,
            batch_size=args.batch_size,
            num_epochs=args.num_epochs,
            base_lr=args.base_lr,
            output_dir=args.output_dir,
            device=args.device,
            seed=args.seed,
        )

    return config


DEFAULT_CONFIG = TrainingConfig()


PRESET_CONFIGS = {
    "fast": TrainingConfig(
        model=ModelConfig(
            enable_mhc=True,
            num_mhc_blocks=1,
            projection_interval=200,
            sinkhorn_iterations=3,
        ),
        mhc=MHCConfig(
            projection_interval=200,
            sinkhorn_iterations=3,
        ),
        batch_size=16,
        num_epochs=2,
    ),

    "balanced": TrainingConfig(
        model=ModelConfig(
            enable_mhc=True,
            num_mhc_blocks=2,
            projection_interval=500,
            sinkhorn_iterations=5,
        ),
        mhc=MHCConfig(
            projection_interval=500,
            sinkhorn_iterations=5,
        ),
        batch_size=8,
        num_epochs=3,
    ),

    "quality": TrainingConfig(
        model=ModelConfig(
            enable_mhc=True,
            num_mhc_blocks=3,
            projection_interval=1000,
            sinkhorn_iterations=10,
            mhc_hidden_ratio=2.0,
        ),
        mhc=MHCConfig(
            projection_interval=1000,
            sinkhorn_iterations=10,
        ),
        batch_size=4,
        num_epochs=5,
    ),
}


def get_preset(name: str) -> TrainingConfig:
    """获取预设配置。

    Args:
        name: 预设名称 (fast, balanced, quality)

    Returns:
        对应的训练配置
    """
    if name not in PRESET_CONFIGS:
        raise ValueError(f"未知预设: {name}，可用: {list(PRESET_CONFIGS.keys())}")
    return PRESET_CONFIGS[name]


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--list-presets":
        print("可用预设配置:")
        for name in PRESET_CONFIGS:
            print(f"  - {name}")
        sys.exit(0)

    config = parse_args()
    print("训练配置:")
    print(json.dumps(config.to_dict(), indent=2, ensure_ascii=False))
