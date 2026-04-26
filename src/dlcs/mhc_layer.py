"""
mHC (Manifold-Constrained Hyper-Connections) 模块

基于 UDMA 论文中的流形约束超连接设计：
- Sinkhorn 投影将混合矩阵投影到双随机矩阵流形
- 保持信号守恒和范数控制
- 支持残差连接的稳定性和表达能力平衡

参考: Xie et al., arXiv:2512.24880v2
"""
from __future__ import annotations

import math
from typing import Optional, Tuple
import logging

import torch
import torch.nn as nn
import torch.nn.functional as F


class SinkhornProjector:
    """Sinkhorn 投影器 - 将矩阵投影到双随机矩阵流形。

    双随机矩阵特点：
    1. 行和为 1
    2. 列和为 1
    3. 所有元素非负

    这保证了信号在深层传播时保持守恒（均值不变）。
    """

    def __init__(
        self,
        iterations: int = 5,
        temperature: float = 0.1,
        entropy_regularization: float = 0.01,
        learnable: bool = False,
    ):
        """
        Args:
            iterations: Sinkhorn 迭代次数 (K)
            temperature: 温度参数，控制分布平滑度
            entropy_regularization: 熵正则化系数 (τ)
            learnable: 是否将投影参数设为可学习
        """
        self.iterations = iterations
        self.temperature = temperature
        self.entropy_reg = entropy_regularization
        self.learnable = learnable

    def project(self, matrix: torch.Tensor, warm_start: Optional[torch.Tensor] = None) -> torch.Tensor:
        """对矩阵进行 Sinkhorn 投影。

        Args:
            matrix: 输入矩阵 (..., H, H)，可以是任意形状
            warm_start: 热启动矩阵，如果提供则加速收敛

        Returns:
            投影后的双随机矩阵 (..., H, H)
        """
        if self.learnable and warm_start is not None:
            return self._learnable_projection(matrix, warm_start)

        return self._sinkhorn_iteration(matrix)

    def _sinkhorn_iteration(self, matrix: torch.Tensor) -> torch.Tensor:
        """标准的 Sinkhorn-Knopp 交替归一化迭代。"""
        H = matrix.size(-1)
        result = matrix

        for _ in range(self.iterations):
            row_sum = result.sum(dim=-1, keepdim=True).clamp(min=1e-9)
            result = result / row_sum

            col_sum = result.sum(dim=-2, keepdim=True).clamp(min=1e-9)
            result = result / col_sum

        result = F.relu(result).clamp(max=1e9)
        return result

    def _learnable_projection(
        self, matrix: torch.Tensor, warm_start: torch.Tensor
    ) -> torch.Tensor:
        """可学习的投影，结合热启动和可调参数。"""
        base = self._sinkhorn_iteration(matrix)

        if warm_start is not None:
            alpha = 0.9
            base = alpha * warm_start + (1 - alpha) * base

        return base


class ManifoldConstrainedLinear(nn.Module):
    """流形约束线性层 - 结合 mHC 和标准线性变换。

    该层将输入 x 通过混合矩阵 H 进行线性变换，同时保持流形约束：
    1. 如果启用 mHC，使用 Sinkhorn 投影的混合矩阵
    2. 否则使用标准线性变换
    3. 支持残差连接
    """

    def __init__(
        self,
        in_features: int,
        out_features: int,
        bias: bool = True,
        enable_mhc: bool = True,
        mhc_hidden_ratio: float = 1.5,
        sinkhorn_iterations: int = 5,
        sinkhorn_temperature: float = 0.1,
        projection_interval: int = 500,
        residual_scale: float = 0.1,
    ):
        """
        Args:
            in_features: 输入维度
            out_features: 输出维度
            bias: 是否使用偏置
            enable_mhc: 是否启用 mHC
            mhc_hidden_ratio: mHC 隐藏层维度比例
            sinkhorn_iterations: Sinkhorn 投影迭代次数
            sinkhorn_temperature: Sinkhorn 温度参数
            projection_interval: 投影更新间隔（训练步数）
            residual_scale: 残差连接缩放因子
        """
        super().__init__()

        self.in_features = in_features
        self.out_features = out_features
        self.enable_mhc = enable_mhc
        self.projection_interval = projection_interval
        self.residual_scale = residual_scale

        self.linear = nn.Linear(in_features, out_features, bias)

        if enable_mhc:
            self.mhc_hidden_dim = max(1, int(in_features * mhc_hidden_ratio))
            self.mhc_hidden_dim = max(1, int(math.sqrt(self.mhc_hidden_dim * out_features)))

            self.hyper_matrix = nn.Parameter(
                torch.randn(in_features, self.mhc_hidden_dim) * 0.01
            )
            self.hyper_output = nn.Parameter(
                torch.randn(self.mhc_hidden_dim, out_features) * 0.01
            )

            self.sinkhorn = SinkhornProjector(
                iterations=sinkhorn_iterations,
                temperature=sinkhorn_temperature,
                learnable=False,
            )

            self._prev_projection: Optional[torch.Tensor] = None
            self._step_counter = 0

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """前向传播。

        Args:
            x: 输入张量 (batch, seq, in_features)

        Returns:
            输出张量 (batch, seq, out_features)
        """
        base_output = self.linear(x)

        if not self.enable_mhc:
            return base_output

        self._step_counter += 1

        if self._step_counter % self.projection_interval == 0 or self._prev_projection is None:
            self._update_projection()

        if self._prev_projection is not None:
            h_matrix = self._prev_projection
            if h_matrix.size(0) == x.size(-1) and h_matrix.size(1) == x.size(-1):
                h_scaled = h_matrix * self.residual_scale
                residual = torch.matmul(x, h_scaled)
                return base_output + residual

        return base_output

    def _update_projection(self) -> None:
        """更新 mHC 投影矩阵。"""
        raw_matrix = torch.matmul(self.hyper_matrix, self.hyper_output)

        H, W = raw_matrix.size()
        if H == W:
            projected = self.sinkhorn.project(raw_matrix, self._prev_projection)
        else:
            combined = torch.matmul(raw_matrix, raw_matrix.t())
            projected = self.sinkhorn.project(combined, self._prev_projection)

        self._prev_projection = projected.detach().clone()
        logging.getLogger(__name__).debug(
            f"mHC projection updated, matrix shape: {projected.shape}"
        )

    def get_projection_matrix(self) -> Optional[torch.Tensor]:
        """获取当前的投影矩阵（用于分析）。"""
        return self._prev_projection

    def extra_repr(self) -> str:
        return (
            f"in_features={self.in_features}, "
            f"out_features={self.out_features}, "
            f"enable_mhc={self.enable_mhc}"
        )


class MHCResidualBlock(nn.Module):
    """mHC 残差块 - 增强深度网络的残差连接。

    结合了：
    1. 流形约束的残差混合
    2. 标准前向传播
    3. 可选的层归一化
    """

    def __init__(
        self,
        dim: int,
        hidden_dim: Optional[int] = None,
        dropout: float = 0.1,
        enable_mhc: bool = True,
        num_mhc_layers: int = 2,
        residual_scale: float = 0.1,
    ):
        """
        Args:
            dim: 输入/输出维度
            hidden_dim: 前向隐藏层维度，默认 4*dim
            dropout: Dropout 概率
            enable_mhc: 是否启用 mHC
            num_mhc_layers: mHC 层数量
            residual_scale: 残差缩放因子
        """
        super().__init__()

        hidden_dim = hidden_dim or 4 * dim
        self.enable_mhc = enable_mhc
        self.residual_scale = residual_scale

        self.norm1 = nn.LayerNorm(dim)
        self.norm2 = nn.LayerNorm(dim)

        self.linear1 = nn.Linear(dim, hidden_dim)
        self.linear2 = nn.Linear(hidden_dim, dim)

        self.mhc_layers = nn.ModuleList([
            ManifoldConstrainedLinear(
                dim, dim,
                enable_mhc=enable_mhc,
                residual_scale=residual_scale,
            )
            for _ in range(num_mhc_layers)
        ])

        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """前向传播。

        Args:
            x: 输入张量 (batch, seq, dim)

        Returns:
            输出张量 (batch, seq, dim)
        """
        residual = x

        h = self.norm1(x)
        h = self.linear1(h)
        h = F.gelu(h)
        h = self.dropout(h)
        h = self.linear2(h)
        h = self.dropout(h)

        x = residual + h * self.residual_scale

        if self.enable_mhc:
            mhc_out = x
            for mhc_layer in self.mhc_layers:
                mhc_out = mhc_layer(mhc_out)
            x = x + mhc_out * self.residual_scale

        return x
