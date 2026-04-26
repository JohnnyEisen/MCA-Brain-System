"""
硬件检测和优化模块

针对不同硬件配置提供最优策略：
1. 核显 (iGPU) - 低功耗，适合轻量推理
2. 独显 (dGPU) - 高性能，适合大规模训练
3. CPU only - 纯 CPU 推理

参考: UDMA 论文 - Xie et al., arXiv:2512.24880v2
"""
from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from typing import Optional, Tuple
from enum import Enum

import torch

logger = logging.getLogger(__name__)


class HardwareType(Enum):
    """硬件类型枚举。"""
    CPU = "cpu"
    INTEGRATED_GPU = "integrated_gpu"
    DEDICATED_GPU = "dedicated_gpu"


@dataclass
class HardwareConfig:
    """硬件配置。"""

    hardware_type: HardwareType
    device_name: str
    total_memory_gb: float
    available_memory_gb: float
    num_cores: int
    supports_fp16: bool
    supports_bf16: bool
    supports_mixed_precision: bool

    recommended_dtype: str
    max_batch_size: int
    use_half_precision: bool
    gradient_checkpointing: bool
    cpu_offload: bool


def get_hardware_info() -> HardwareConfig:
    """检测硬件信息并返回优化配置。

    Returns:
        HardwareConfig: 硬件配置
    """
    device_name = "Unknown"
    total_memory_gb = 0.0
    available_memory_gb = 0.0
    num_cores = os.cpu_count() or 4

    hardware_type = HardwareType.CPU
    supports_fp16 = False
    supports_bf16 = False
    supports_mixed_precision = False

    if torch.cuda.is_available():
        try:
            device_name = torch.cuda.get_device_name(0)
            total_memory_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            available_memory_gb = total_memory_gb

            if torch.cuda.is_initialized():
                try:
                    available_memory_gb = torch.cuda.mem_get_info()[0] / (1024 ** 3)
                except Exception:
                    available_memory_gb = total_memory_gb * 0.8

            hardware_type = HardwareType.DEDICATED_GPU

            cuda_capability = torch.cuda.get_device_capability(0)
            supports_fp16 = cuda_capability[0] >= 7.0
            supports_bf16 = cuda_capability[0] >= 8.0
            supports_mixed_precision = True

            logger.info(f"检测到独显: {device_name}")
            logger.info(f"  总内存: {total_memory_gb:.1f} GB")
            logger.info(f"  可用内存: {available_memory_gb:.1f} GB")
            logger.info(f"  计算能力: {cuda_capability[0]}.{cuda_capability[1]}")
            logger.info(f"  FP16 支持: {supports_fp16}")
            logger.info(f"  BF16 支持: {supports_bf16}")

        except Exception as e:
            logger.warning(f"CUDA 检测失败: {e}")
            hardware_type = HardwareType.CPU

    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        hardware_type = HardwareType.INTEGRATED_GPU
        device_name = "Apple MPS"
        supports_fp16 = True
        logger.info("检测到 Apple MPS (核显)")

    else:
        device_name = f"CPU ({num_cores} cores)"
        hardware_type = HardwareType.CPU
        logger.info(f"仅检测到 CPU: {device_name}")

    recommended_dtype, max_batch_size, use_half, grad_ckpt, cpu_offload = get_hardware_optimization(
        hardware_type, available_memory_gb
    )

    return HardwareConfig(
        hardware_type=hardware_type,
        device_name=device_name,
        total_memory_gb=total_memory_gb,
        available_memory_gb=available_memory_gb,
        num_cores=num_cores,
        supports_fp16=supports_fp16,
        supports_bf16=supports_bf16,
        supports_mixed_precision=supports_mixed_precision,
        recommended_dtype=recommended_dtype,
        max_batch_size=max_batch_size,
        use_half_precision=use_half,
        gradient_checkpointing=grad_ckpt,
        cpu_offload=cpu_offload,
    )


def get_hardware_optimization(
    hardware_type: HardwareType,
    available_memory_gb: float
) -> Tuple[str, int, bool, bool, bool]:
    """根据硬件类型获取优化参数。

    Args:
        hardware_type: 硬件类型
        available_memory_gb: 可用内存（GB）

    Returns:
        (recommended_dtype, max_batch_size, use_half_precision, gradient_checkpointing, cpu_offload)
    """
    if hardware_type == HardwareType.DEDICATED_GPU:
        if available_memory_gb >= 16:
            return "float32", 32, True, False, False
        elif available_memory_gb >= 8:
            return "float32", 16, True, False, False
        elif available_memory_gb >= 4:
            return "float16", 8, True, True, False
        else:
            return "float16", 4, True, True, True

    elif hardware_type == HardwareType.INTEGRATED_GPU:
        if available_memory_gb >= 8:
            return "float16", 8, True, False, False
        elif available_memory_gb >= 4:
            return "float16", 4, True, True, False
        else:
            return "float16", 2, True, True, True

    else:
        if available_memory_gb >= 16:
            return "float32", 16, False, False, False
        elif available_memory_gb >= 8:
            return "float32", 8, False, False, False
        elif available_memory_gb >= 4:
            return "float32", 4, False, True, False
        else:
            return "float32", 2, False, True, True


def get_device_for_inference(hardware_config: Optional[HardwareConfig] = None) -> torch.device:
    """获取推理设备。

    Args:
        hardware_config: 硬件配置，如果为 None 则自动检测

    Returns:
        torch.device
    """
    if hardware_config is None:
        hardware_config = get_hardware_info()

    if hardware_config.hardware_type == HardwareType.DEDICATED_GPU:
        return torch.device("cuda")
    elif hardware_config.hardware_type == HardwareType.INTEGRATED_GPU:
        return torch.device("mps" if hasattr(torch.backends.mps, "is_available") and torch.backends.mps.is_available() else "cpu")
    else:
        return torch.device("cpu")


def create_optimizer_for_hardware(
    model: torch.nn.Module,
    hardware_config: Optional[HardwareConfig] = None,
    base_lr: float = 1e-4,
) -> torch.optim.Optimizer:
    """根据硬件配置创建优化器。

    Args:
        model: 模型
        hardware_config: 硬件配置
        base_lr: 基础学习率

    Returns:
        优化器实例
    """
    if hardware_config is None:
        hardware_config = get_hardware_info()

    if hardware_config.hardware_type == HardwareType.CPU:
        return torch.optim.AdamW(
            filter(lambda p: p.requires_grad, model.parameters()),
            lr=base_lr,
            weight_decay=0.01,
        )
    else:
        return torch.optim.AdamW(
            filter(lambda p: p.requires_grad, model.parameters()),
            lr=base_lr,
            weight_decay=0.01,
            betas=(0.9, 0.999),
            eps=1e-8,
        )


def apply_hardware_optimizations(
    model: torch.nn.Module,
    hardware_config: Optional[HardwareConfig] = None,
) -> torch.nn.Module:
    """应用硬件特定优化。

    Args:
        model: 模型
        hardware_config: 硬件配置

    Returns:
        优化后的模型
    """
    if hardware_config is None:
        hardware_config = get_hardware_info()

    if hardware_config.hardware_type != HardwareType.CPU:
        if hardware_config.use_half_precision:
            model = model.half()
            logger.info("已启用半精度 (FP16)")

        if hardware_config.gradient_checkpointing:
            if hasattr(model, 'enable_gradient_checkpointing'):
                model.enable_gradient_checkpointing()
                logger.info("已启用梯度检查点")

    if hardware_config.cpu_offload:
        logger.info("已启用 CPU 卸载")

    return model


class MixedPrecisionManager:
    """混合精度管理器。"""

    def __init__(self, enabled: bool = True, device_type: str = "cuda"):
        """
        Args:
            enabled: 是否启用混合精度
            device_type: 设备类型
        """
        self.enabled = enabled and torch.cuda.is_available()
        self.device_type = device_type
        self.scaler = None

        if self.enabled:
            self.scaler = torch.cuda.amp.GradScaler()

    def __enter__(self):
        if self.enabled:
            self.autocast = torch.cuda.amp.autocast()
            self.autocast.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.enabled:
            self.autocast.__exit__(exc_type, exc_val, exc_tb)
        return False

    def scale_loss(self, loss: torch.Tensor) -> torch.Tensor:
        """缩放损失值。"""
        if self.enabled and self.scaler is not None:
            return self.scaler.scale(loss)
        return loss

    def step(self, optimizer: torch.optim.Optimizer):
        """执行优化步骤。"""
        if self.enabled and self.scaler is not None:
            self.scaler.step(optimizer)
            self.scaler.update()


def optimize_for_hardware(
    model: torch.nn.Module,
    hardware_config: Optional[HardwareConfig] = None,
) -> Tuple[torch.nn.Module, HardwareConfig, MixedPrecisionManager]:
    """综合硬件优化。

    Args:
        model: 模型

    Returns:
        (优化后的模型, 硬件配置, 混合精度管理器)
    """
    if hardware_config is None:
        hardware_config = get_hardware_info()

    model = apply_hardware_optimizations(model, hardware_config)

    mixed_precision = MixedPrecisionManager(
        enabled=hardware_config.use_half_precision,
        device_type=str(hardware_config.hardware_type.value)
    )

    return model, hardware_config, mixed_precision
