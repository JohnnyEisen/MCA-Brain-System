"""
mHC 训练器 - 用于微调 CodeBERT 模型

提供：
1. mHC-Aware 优化器
2. 投影调度器
3. 梯度裁剪和稳定化
4. 流形约束损失

参考: UDMA 论文 - Xie et al., arXiv:2512.24880v2
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Callable, List, Dict, Any
import logging

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import Optimizer
from torch.optim.lr_scheduler import LambdaLR


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


class ManifoldConstrainedOptimizer(nn.Module):
    """包装优化器，支持 mHC 特定参数组。

    为 mHC 参数（hyper_matrix, sinkhorn）设置不同的学习率和权重衰减。
    """

    def __init__(
        self,
        model: nn.Module,
        base_lr: float = 1e-4,
        mhc_config: Optional[MHCConfig] = None,
        betas: tuple = (0.9, 0.999),
        eps: float = 1e-8,
    ):
        """
        Args:
            model: 包含 mHC 层的模型
            base_lr: 基础学习率
            mhc_config: mHC 配置
            betas: Adam betas
            eps: Adam epsilon
        """
        super().__init__()
        self.model = model
        self.base_lr = base_lr
        self.mhc_config = mhc_config or MHCConfig()

        self.param_groups = self._prepare_param_groups()

        self.optimizer = torch.optim.AdamW(
            self.param_groups,
            lr=base_lr,
            betas=betas,
            eps=eps,
        )

    def _prepare_param_groups(self) -> List[Dict[str, Any]]:
        """分离 mHC 参数和普通参数。"""
        mhc_params = []
        other_params = []

        for name, param in self.model.named_parameters():
            if 'hyper_matrix' in name or 'sinkhorn' in name or 'mhc' in name.lower():
                mhc_params.append(param)
            else:
                other_params.append(param)

        groups = [
            {'params': other_params, 'lr': self.base_lr},
        ]

        if mhc_params:
            mhc_lr = self.base_lr * self.mhc_config.mhc_lr_ratio
            groups.append({
                'params': mhc_params,
                'lr': mhc_lr,
                'weight_decay': self.mhc_config.mhc_weight_decay,
            })

        return groups

    def step(self) -> None:
        """执行优化步骤。"""
        self.optimizer.step()

    def zero_grad(self) -> None:
        """清零梯度。"""
        self.optimizer.zero_grad()

    def get_lr(self) -> float:
        """获取当前学习率。"""
        return self.optimizer.param_groups[0]['lr']


class ProjectionScheduler:
    """投影间隔调度器 - 根据训练进度调整投影频率。

    UDMA 建议：
    - 训练初期：频繁投影（100 步）以快速稳定
    - 训练后期：降低频率（500+ 步）以节省计算
    """

    def __init__(
        self,
        initial_interval: int = 100,
        final_interval: int = 500,
        warmup_steps: int = 1000,
    ):
        """
        Args:
            initial_interval: 初始投影间隔
            final_interval: 最终投影间隔
            warmup_steps: 热身步数
        """
        self.initial_interval = initial_interval
        self.final_interval = final_interval
        self.warmup_steps = warmup_steps

    def get_interval(self, step: int) -> int:
        """获取当前步的投影间隔。

        使用余弦衰减从 initial_interval 过渡到 final_interval。
        """
        if step < self.warmup_steps:
            return self.initial_interval

        progress = (step - self.warmup_steps) / max(1, 10000 - self.warmup_steps)
        progress = min(progress, 1.0)

        cosine_decay = 0.5 * (1 + math.cos(math.pi * progress))
        interval = self.initial_interval + cosine_decay * (self.final_interval - self.initial_interval)

        return int(interval)


class MHCGradientClipper:
    """mHC 梯度裁剪器 - 稳定训练。

    特性：
    1. 按范数裁剪
    2. 检测梯度爆炸
    3. 可选的对角加罚
    """

    def __init__(
        self,
        max_norm: float = 1.0,
        norm_type: float = 2.0,
        penalty_coef: float = 0.01,
    ):
        """
        Args:
            max_norm: 最大梯度范数
            norm_type: 范数类型
            penalty_coef: 对角加罚系数
        """
        self.max_norm = max_norm
        self.norm_type = norm_type
        self.penalty_coef = penalty_coef

    def clip_gradients(self, model: nn.Module) -> float:
        """裁剪梯度并返回裁剪后的范数。"""
        total_norm = torch.nn.utils.clip_grad_norm_(
            model.parameters(),
            self.max_norm,
            norm_type=self.norm_type,
        )
        return total_norm.item()

    def compute_diagonal_penalty(self, model: nn.Module) -> torch.Tensor:
        """计算对角加罚项 - 鼓励混合矩阵接近双随机。

        损失 = ||X @ 1 - 1||^2 + ||X^T @ 1 - 1||^2
        """
        penalty = torch.tensor(0.0, device=next(model.parameters()).device)

        for name, param in model.named_parameters():
            if 'hyper_matrix' in name or 'hyper_output' in name:
                if param.dim() >= 2:
                    row_sum = param.sum(dim=-1)
                    col_sum = param.sum(dim=-2)
                    penalty = penalty + F.mse_loss(row_sum, torch.ones_like(row_sum))
                    penalty = penalty + F.mse_loss(col_sum, torch.ones_like(col_sum))

        return penalty * self.penalty_coef


def create_mhc_trainer(
    model: nn.Module,
    base_lr: float = 1e-4,
    mhc_config: Optional[MHCConfig] = None,
) -> 'MHCTrainer':
    """创建 mHC 训练器的工厂函数。"""
    return MHCTrainer(model, base_lr, mhc_config)


class MHCTrainer:
    """mHC 训练器 - 整合所有训练组件。

    使用方式：
    ```python
    trainer = create_mhc_trainer(model, base_lr=1e-4)
    for batch in dataloader:
        loss = model(batch)
        trainer.step(loss)
    ```
    """

    def __init__(
        self,
        model: nn.Module,
        base_lr: float = 1e-4,
        mhc_config: Optional[MHCConfig] = None,
    ):
        """
        Args:
            model: 要训练的模型
            base_lr: 基础学习率
            mhc_config: mHC 配置
        """
        self.model = model
        self.mhc_config = mhc_config or MHCConfig()

        self.optimizer = ManifoldConstrainedOptimizer(
            model, base_lr, self.mhc_config
        )
        self.scheduler = ProjectionScheduler(
            initial_interval=self.mhc_config.projection_interval,
            final_interval=self.mhc_config.projection_interval * 2,
            warmup_steps=self.mhc_config.warmup_steps,
        )
        self.grad_clipper = MHCGradientClipper(
            max_norm=self.mhc_config.gradient_clip_norm,
            penalty_coef=self.mhc_config.entropy_regularization,
        )

        self.step_count = 0
        self.loss_history: List[float] = []

    def step(self, loss: torch.Tensor, retain_graph: bool = False) -> Dict[str, float]:
        """执行单个训练步骤。

        Args:
            loss: 损失值
            retain_graph: 是否保留计算图

        Returns:
            训练统计信息
        """
        self.step_count += 1

        loss_value = loss.item()
        self.loss_history.append(loss_value)

        diag_penalty = self.grad_clipper.compute_diagonal_penalty(self.model)
        total_loss = loss + diag_penalty

        total_loss.backward(retain_graph=retain_graph)

        grad_norm = self.grad_clipper.clip_gradients(self.model)

        self.optimizer.step()
        self.optimizer.zero_grad()

        projection_interval = self.scheduler.get_interval(self.step_count)

        stats = {
            'step': self.step_count,
            'loss': loss_value,
            'penalty': diag_penalty.item(),
            'grad_norm': grad_norm,
            'lr': self.optimizer.get_lr(),
            'projection_interval': projection_interval,
        }

        if self.step_count % 100 == 0:
            logging.info(
                f"Step {self.step_count} | Loss: {loss_value:.4f} | "
                f"Grad: {grad_norm:.4f} | LR: {stats['lr']:.2e}"
            )

        return stats

    def get_projection_stats(self) -> Dict[str, Any]:
        """获取投影矩阵统计信息（用于分析）。"""
        stats = {}
        for name, module in self.model.named_modules():
            if isinstance(module, torch.nn.Module):
                if hasattr(module, 'get_projection_matrix'):
                    proj = module.get_projection_matrix()
                    if proj is not None:
                        stats[name] = {
                            'shape': list(proj.shape),
                            'mean': proj.mean().item(),
                            'std': proj.std().item(),
                            'min': proj.min().item(),
                            'max': proj.max().item(),
                        }
        return stats

    def save_checkpoint(self, path: str) -> None:
        """保存训练检查点。"""
        checkpoint = {
            'step': self.step_count,
            'loss_history': self.loss_history[-1000:],
            'model_state': self.model.state_dict(),
            'optimizer_state': self.optimizer.optimizer.state_dict(),
            'mhc_config': self.mhc_config,
        }
        torch.save(checkpoint, path)
        logging.info(f"Checkpoint saved to {path}")

    def load_checkpoint(self, path: str) -> None:
        """加载训练检查点。"""
        checkpoint = torch.load(path, map_location='cpu')
        self.model.load_state_dict(checkpoint['model_state'])
        self.optimizer.optimizer.load_state_dict(checkpoint['optimizer_state'])
        self.step_count = checkpoint['step']
        self.loss_history = checkpoint.get('loss_history', [])
        logging.info(f"Checkpoint loaded from {path}")
