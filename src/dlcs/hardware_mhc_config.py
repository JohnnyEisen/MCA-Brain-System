"""
硬件特定 mHC 配置

根据不同硬件配置提供最优的 mHC 参数：
1. CPU - 轻量级 mHC，减少计算
2. iGPU - 平衡模式，启用部分优化
3. dGPU - 完整 mHC，充分利用硬件

参考: UDMA 论文 - Xie et al., arXiv:2512.24880v2
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from dlcs.hardware_utils import HardwareType


@dataclass
class HardwareAwareMHCConfig:
    """硬件感知的 mHC 配置。"""

    hardware_type: HardwareType
    available_memory_gb: float

    num_mhc_blocks: int
    mhc_hidden_ratio: float
    sinkhorn_iterations: int
    projection_interval: int
    residual_scale: float

    batch_size: int
    max_sequence_length: int

    enable_gradient_checkpointing: bool
    use_cpu_offload: bool
    use_mixed_precision: bool

    base_lr: float
    mhc_lr_ratio: float


def get_mhc_config_for_hardware(
    hardware_type: HardwareType,
    available_memory_gb: float,
    task: str = "inference",
) -> HardwareAwareMHCConfig:
    """根据硬件获取最优 mHC 配置。

    Args:
        hardware_type: 硬件类型
        available_memory_gb: 可用内存（GB）
        task: 任务类型 ("inference", "fine_tuning", "training")

    Returns:
        HardwareAwareMHCConfig: 硬件感知配置
    """
    if hardware_type == HardwareType.DEDICATED_GPU:
        return _get_dgpu_mhc_config(available_memory_gb, task)
    elif hardware_type == HardwareType.INTEGRATED_GPU:
        return _get_igpu_mhc_config(available_memory_gb, task)
    else:
        return _get_cpu_mhc_config(available_memory_gb, task)


def _get_dgpu_mhc_config(memory_gb: float, task: str) -> HardwareAwareMHCConfig:
    """独显 (dGPU) 的 mHC 配置。

    配置策略：
    - 16GB+: 完整 mHC，2-3 个块，高投影频率
    - 8GB: 平衡 mHC，2 个块
    - 4GB: 轻量 mHC，1 个块，低投影频率
    """
    if memory_gb >= 16:
        return HardwareAwareMHCConfig(
            hardware_type=HardwareType.DEDICATED_GPU,
            available_memory_gb=memory_gb,
            num_mhc_blocks=3,
            mhc_hidden_ratio=2.0,
            sinkhorn_iterations=10,
            projection_interval=500,
            residual_scale=0.1,
            batch_size=32 if task == "inference" else 8,
            max_sequence_length=512,
            enable_gradient_checkpointing=False,
            use_cpu_offload=False,
            use_mixed_precision=True,
            base_lr=1e-4,
            mhc_lr_ratio=0.1,
        )
    elif memory_gb >= 8:
        return HardwareAwareMHCConfig(
            hardware_type=HardwareType.DEDICATED_GPU,
            available_memory_gb=memory_gb,
            num_mhc_blocks=2,
            mhc_hidden_ratio=1.5,
            sinkhorn_iterations=5,
            projection_interval=500,
            residual_scale=0.1,
            batch_size=16 if task == "inference" else 4,
            max_sequence_length=512,
            enable_gradient_checkpointing=False,
            use_cpu_offload=False,
            use_mixed_precision=True,
            base_lr=1e-4,
            mhc_lr_ratio=0.1,
        )
    else:
        return HardwareAwareMHCConfig(
            hardware_type=HardwareType.DEDICATED_GPU,
            available_memory_gb=memory_gb,
            num_mhc_blocks=1,
            mhc_hidden_ratio=1.0,
            sinkhorn_iterations=3,
            projection_interval=200,
            residual_scale=0.05,
            batch_size=8 if task == "inference" else 2,
            max_sequence_length=384,
            enable_gradient_checkpointing=True,
            use_cpu_offload=False,
            use_mixed_precision=True,
            base_lr=5e-5,
            mhc_lr_ratio=0.05,
        )


def _get_igpu_mhc_config(memory_gb: float, task: str) -> HardwareAwareMHCConfig:
    """核显 (iGPU) 的 mHC 配置。

    配置策略：
    - 8GB+: 平衡模式，2 个块
    - 4GB: 轻量模式，1 个块
    - <4GB: 极简模式，关闭部分 mHC
    """
    if memory_gb >= 8:
        return HardwareAwareMHCConfig(
            hardware_type=HardwareType.INTEGRATED_GPU,
            available_memory_gb=memory_gb,
            num_mhc_blocks=2,
            mhc_hidden_ratio=1.0,
            sinkhorn_iterations=5,
            projection_interval=500,
            residual_scale=0.1,
            batch_size=8 if task == "inference" else 4,
            max_sequence_length=512,
            enable_gradient_checkpointing=True,
            use_cpu_offload=False,
            use_mixed_precision=True,
            base_lr=5e-5,
            mhc_lr_ratio=0.05,
        )
    elif memory_gb >= 4:
        return HardwareAwareMHCConfig(
            hardware_type=HardwareType.INTEGRATED_GPU,
            available_memory_gb=memory_gb,
            num_mhc_blocks=1,
            mhc_hidden_ratio=1.0,
            sinkhorn_iterations=3,
            projection_interval=300,
            residual_scale=0.05,
            batch_size=4 if task == "inference" else 2,
            max_sequence_length=384,
            enable_gradient_checkpointing=True,
            use_cpu_offload=False,
            use_mixed_precision=True,
            base_lr=5e-5,
            mhc_lr_ratio=0.05,
        )
    else:
        return HardwareAwareMHCConfig(
            hardware_type=HardwareType.INTEGRATED_GPU,
            available_memory_gb=memory_gb,
            num_mhc_blocks=0,
            mhc_hidden_ratio=0.0,
            sinkhorn_iterations=0,
            projection_interval=0,
            residual_scale=0.0,
            batch_size=2 if task == "inference" else 1,
            max_sequence_length=256,
            enable_gradient_checkpointing=True,
            use_cpu_offload=True,
            use_mixed_precision=False,
            base_lr=1e-5,
            mhc_lr_ratio=0.01,
        )


def _get_cpu_mhc_config(memory_gb: float, task: str) -> HardwareAwareMHCConfig:
    """CPU 的 mHC 配置。

    配置策略：
    - 纯 CPU 推理：极简 mHC 或完全关闭
    - 训练：使用 CPU 优化
    """
    if task == "inference":
        if memory_gb >= 16:
            return HardwareAwareMHCConfig(
                hardware_type=HardwareType.CPU,
                available_memory_gb=memory_gb,
                num_mhc_blocks=1,
                mhc_hidden_ratio=1.0,
                sinkhorn_iterations=3,
                projection_interval=500,
                residual_scale=0.05,
                batch_size=4,
                max_sequence_length=512,
                enable_gradient_checkpointing=False,
                use_cpu_offload=False,
                use_mixed_precision=False,
                base_lr=1e-4,
                mhc_lr_ratio=0.1,
            )
        elif memory_gb >= 8:
            return HardwareAwareMHCConfig(
                hardware_type=HardwareType.CPU,
                available_memory_gb=memory_gb,
                num_mhc_blocks=1,
                mhc_hidden_ratio=0.5,
                sinkhorn_iterations=2,
                projection_interval=500,
                residual_scale=0.05,
                batch_size=2,
                max_sequence_length=384,
                enable_gradient_checkpointing=False,
                use_cpu_offload=False,
                use_mixed_precision=False,
                base_lr=1e-4,
                mhc_lr_ratio=0.1,
            )
        else:
            return HardwareAwareMHCConfig(
                hardware_type=HardwareType.CPU,
                available_memory_gb=memory_gb,
                num_mhc_blocks=0,
                mhc_hidden_ratio=0.0,
                sinkhorn_iterations=0,
                projection_interval=0,
                residual_scale=0.0,
                batch_size=1,
                max_sequence_length=256,
                enable_gradient_checkpointing=False,
                use_cpu_offload=False,
                use_mixed_precision=False,
                base_lr=1e-5,
                mhc_lr_ratio=0.01,
            )
    else:
        return HardwareAwareMHCConfig(
            hardware_type=HardwareType.CPU,
            available_memory_gb=memory_gb,
            num_mhc_blocks=1,
            mhc_hidden_ratio=0.5,
            sinkhorn_iterations=2,
            projection_interval=1000,
            residual_scale=0.05,
            batch_size=1,
            max_sequence_length=256,
            enable_gradient_checkpointing=True,
            use_cpu_offload=True,
            use_mixed_precision=False,
            base_lr=1e-5,
            mhc_lr_ratio=0.01,
        )


def create_hardware_aware_model_config(
    base_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    hardware_type: HardwareType = HardwareType.CPU,
    available_memory_gb: float = 8.0,
    task: str = "inference",
) -> Dict[str, Any]:
    """创建硬件感知的完整模型配置。

    Args:
        base_model: 基础模型名称
        hardware_type: 硬件类型
        available_memory_gb: 可用内存（GB）
        task: 任务类型

    Returns:
        完整的模型配置字典
    """
    mhc_config = get_mhc_config_for_hardware(hardware_type, available_memory_gb, task)

    return {
        "base_model": base_model,
        "enable_mhc": mhc_config.num_mhc_blocks > 0,
        "mhc_residual_scale": mhc_config.residual_scale,
        "mhc_hidden_ratio": mhc_config.mhc_hidden_ratio,
        "sinkhorn_iterations": mhc_config.sinkhorn_iterations,
        "sinkhorn_temperature": 0.1,
        "projection_interval": mhc_config.projection_interval,
        "num_mhc_blocks": mhc_config.num_mhc_blocks,
        "mhc_dropout": 0.1,
        "trainable": task != "inference",
        "batch_size": mhc_config.batch_size,
        "max_length": mhc_config.max_sequence_length,
        "use_mixed_precision": mhc_config.use_mixed_precision,
        "enable_gradient_checkpointing": mhc_config.enable_gradient_checkpointing,
        "use_cpu_offload": mhc_config.use_cpu_offload,
        "base_lr": mhc_config.base_lr,
        "mhc_lr_ratio": mhc_config.mhc_lr_ratio,
    }


PRESET_MHC_CONFIGS = {
    "cpu_inference": _get_cpu_mhc_config(8, "inference"),
    "cpu_training": _get_cpu_mhc_config(16, "training"),
    "igpu_inference": _get_igpu_mhc_config(4, "inference"),
    "igpu_training": _get_igpu_mhc_config(8, "training"),
    "dgpu_inference": _get_dgpu_mhc_config(8, "inference"),
    "dgpu_training": _get_dgpu_mhc_config(16, "training"),
}


def get_preset_mhc_config(preset_name: str) -> HardwareAwareMHCConfig:
    """获取预设的 mHC 配置。

    Args:
        preset_name: 预设名称

    Returns:
        HardwareAwareMHCConfig

    Raises:
        ValueError: 未知预设名称
    """
    if preset_name not in PRESET_MHC_CONFIGS:
        raise ValueError(
            f"未知预设: {preset_name}，可用: {list(PRESET_MHC_CONFIGS.keys())}"
        )
    return PRESET_MHC_CONFIGS[preset_name]
