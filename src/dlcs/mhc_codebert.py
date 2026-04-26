"""
MHCCodeBert - 集成 mHC 的 CodeBERT 模型

将流形约束超连接（mHC）集成到 CodeBERT 架构中：
1. 在 Transformer 层之间插入 mHC 残差块
2. 支持 mHC-aware 训练
3. 保持与原始 CodeBERT 的兼容性
4. 支持硬件感知优化（CPU/iGPU/dGPU）

参考: UDMA 论文 - Xie et al., arXiv:2512.24880v2
"""
from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    import transformers
    from transformers import AutoModel, AutoTokenizer, AutoConfig
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    transformers = None
    AutoModel = None
    AutoTokenizer = None
    AutoConfig = None

from dlcs.mhc_layer import (
    ManifoldConstrainedLinear,
    MHCResidualBlock,
    SinkhornProjector,
)
from dlcs.mhc_trainer import MHCConfig, MHCTrainer, create_mhc_trainer
from dlcs.hardware_utils import (
    HardwareConfig,
    HardwareType,
    get_hardware_info,
    get_device_for_inference,
    optimize_for_hardware,
    MixedPrecisionManager,
)


@dataclass
class MHCCodeBertConfig:
    """mHC 增强的 CodeBERT 配置。"""

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


class MHCCodeBert(nn.Module):
    """集成 mHC 的 CodeBERT 模型。

    架构：
    1. 基础 Transformer 编码器（冻结或可训练）
    2. mHC 残差块（可训练）
    3. 语义聚合层
    4. 硬件感知优化
    """

    def __init__(
        self,
        config: Optional[MHCCodeBertConfig] = None,
        hardware_config: Optional[HardwareConfig] = None,
    ):
        """
        Args:
            config: mHC CodeBERT 配置
            hardware_config: 硬件配置，如果为 None 则自动检测
        """
        super().__init__()

        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("transformers 库未安装，请运行: pip install transformers")

        self.hardware_config = hardware_config or get_hardware_info()

        logging.info(f"硬件配置: {self.hardware_config.hardware_type.value}")
        logging.info(f"  设备: {self.hardware_config.device_name}")
        logging.info(f"  可用内存: {self.hardware_config.available_memory_gb:.1f} GB")
        logging.info(f"  推荐精度: {self.hardware_config.recommended_dtype}")

        if config is None:
            from dlcs.hardware_mhc_config import get_mhc_config_for_hardware
            mhc_cfg = get_mhc_config_for_hardware(
                self.hardware_config.hardware_type,
                self.hardware_config.available_memory_gb,
                "inference"
            )
            config = MHCCodeBertConfig(
                base_model="sentence-transformers/all-MiniLM-L6-v2",
                enable_mhc=mhc_cfg.num_mhc_blocks > 0,
                mhc_residual_scale=mhc_cfg.residual_scale,
                mhc_hidden_ratio=mhc_cfg.mhc_hidden_ratio,
                sinkhorn_iterations=mhc_cfg.sinkhorn_iterations,
                projection_interval=mhc_cfg.projection_interval,
                num_mhc_blocks=mhc_cfg.num_mhc_blocks,
            )
            logging.info(f"自动配置 mHC: {mhc_cfg.num_mhc_blocks} 块")

        self.config = config

        logging.info(f"正在加载基础模型: {config.base_model}")
        self.base_model = AutoModel.from_pretrained(config.base_model)
        self.tokenizer = AutoTokenizer.from_pretrained(config.base_model)

        hidden_size = self.base_model.config.hidden_size
        num_layers = self.base_model.config.num_hidden_layers

        if not config.fine_tune_base:
            for param in self.base_model.parameters():
                param.requires_grad = False

        self.projection_layers = nn.ModuleList()

        if config.enable_mhc:
            logging.info(f"添加 {config.num_mhc_blocks} 个 mHC 残差块")

            for i in range(config.num_mhc_blocks):
                mhc_block = MHCResidualBlock(
                    dim=hidden_size,
                    hidden_dim=int(hidden_size * config.mhc_hidden_ratio),
                    dropout=config.mhc_dropout,
                    enable_mhc=True,
                    residual_scale=config.mhc_residual_scale,
                )
                self.projection_layers.append(mhc_block)

        self.norm = nn.LayerNorm(hidden_size)

        self.device = get_device_for_inference(self.hardware_config)
        self.mixed_precision = MixedPrecisionManager(
            enabled=self.hardware_config.use_half_precision,
            device_type=str(self.device),
        )

        self._is_ready = False

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        token_type_ids: Optional[torch.Tensor] = None,
        return_embeddings: bool = False,
    ) -> torch.Tensor:
        """前向传播。

        Args:
            input_ids: 输入 token IDs
            attention_mask: 注意力掩码
            token_type_ids: token 类型 IDs
            return_embeddings: 是否直接返回 embeddings

        Returns:
            句子 embeddings (batch, hidden_size)
        """
        base_outputs = self.base_model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
        )

        last_hidden_state = base_outputs.last_hidden_state

        hidden = last_hidden_state
        for mhc_layer in self.projection_layers:
            hidden = mhc_layer(hidden)

        hidden = self.norm(hidden)

        embeddings = self._mean_pooling(hidden, attention_mask)

        embeddings = F.normalize(embeddings, p=2, dim=1)

        return embeddings

    def _mean_pooling(
        self,
        token_embeddings: torch.Tensor,
        attention_mask: torch.Tensor,
    ) -> torch.Tensor:
        """Mean pooling with attention mask."""
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
        sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
        return sum_embeddings / sum_mask

    def encode_text(self, text: str, max_length: int = 510) -> Optional[List[float]]:
        """将文本转换为 embedding 向量。

        Args:
            text: 输入文本
            max_length: 最大 token 长度

        Returns:
            768 维 embedding 向量，或 None（如果失败）
        """
        if not self.training and not self._is_ready:
            self.eval()
            self._is_ready = True

        try:
            tokens = self.tokenizer(
                text,
                max_length=max_length,
                padding=True,
                truncation=True,
                return_tensors="pt",
            )

            input_ids = tokens["input_ids"].to(next(self.parameters()).device)
            attention_mask = tokens["attention_mask"].to(next(self.parameters()).device)

            with torch.no_grad():
                embeddings = self.forward(input_ids, attention_mask)

            return embeddings.cpu().numpy()[0].tolist()

        except Exception as e:
            logging.error(f"Embedding 生成失败: {e}")
            return None

    def get_embedding_dim(self) -> int:
        """获取 embedding 维度。"""
        return self.base_model.config.hidden_size

    def setup_training(
        self,
        base_lr: float = 1e-4,
        mhc_config: Optional[MHCConfig] = None,
    ) -> MHCTrainer:
        """设置 mHC 训练器。

        Args:
            base_lr: 基础学习率
            mhc_config: mHC 训练配置

        Returns:
            MHCTrainer 实例
        """
        if self.config.trainable:
            return create_mhc_trainer(self, base_lr, mhc_config)
        else:
            raise ValueError("模型未启用 trainable 模式")

    def enable_mhc_training(self) -> None:
        """启用 mHC 训练模式。"""
        self.config.trainable = True
        self.train()
        for param in self.projection_layers.parameters():
            param.requires_grad = True

    def freeze_base_model(self) -> None:
        """冻结基础模型。"""
        for param in self.base_model.parameters():
            param.requires_grad = False

    def unfreeze_base_model(self, last_n_layers: int = 2) -> None:
        """解冻基础模型的最后几层。

        Args:
            last_n_layers: 解冻的最后层数
        """
        for param in self.base_model.parameters():
            param.requires_grad = True

        if last_n_layers > 0 and hasattr(self.base_model, 'encoder'):
            layers = self.base_model.encoder.layer
            for i in range(len(layers) - last_n_layers, len(layers)):
                for param in layers[i].parameters():
                    param.requires_grad = False


class MHCCodeBertDLC:
    """mHC CodeBERT DLC - 提供给 BrainCore 使用的 DLC 接口。

    支持硬件自动检测和优化。
    """

    def __init__(
        self,
        config: Optional[MHCCodeBertConfig] = None,
        auto_hardware_optimize: bool = True,
    ):
        """
        Args:
            config: mHC CodeBERT 配置
            auto_hardware_optimize: 是否自动检测硬件并优化
        """
        self.config = config
        self.auto_hardware_optimize = auto_hardware_optimize
        self.model: Optional[MHCCodeBert] = None
        self.trainer: Optional[MHCTrainer] = None
        self.hardware_config: Optional[HardwareConfig] = None

    def initialize(self) -> None:
        """初始化模型。"""
        try:
            import os
            if not os.environ.get("HF_ENDPOINT"):
                os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

            if self.auto_hardware_optimize:
                self.hardware_config = get_hardware_info()
                logging.info("=" * 50)
                logging.info("硬件检测结果:")
                logging.info(f"  类型: {self.hardware_config.hardware_type.value}")
                logging.info(f"  设备: {self.hardware_config.device_name}")
                logging.info(f"  内存: {self.hardware_config.available_memory_gb:.1f} GB")
                logging.info(f"  FP16: {self.hardware_config.supports_fp16}")
                logging.info(f"  推荐精度: {self.hardware_config.recommended_dtype}")
                logging.info("=" * 50)

                self.model = MHCCodeBert(
                    config=self.config,
                    hardware_config=self.hardware_config,
                )
            else:
                self.model = MHCCodeBert(config=self.config)
                self.hardware_config = get_hardware_info()

            self.model.to(self.model.device)
            self.model.eval()

            logging.info("MHCCodeBert 模型加载完成")

        except Exception as e:
            logging.error(f"MHCCodeBert 初始化失败: {e}")
            raise

    def shutdown(self) -> None:
        """关闭并释放资源。"""
        if self.model:
            del self.model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def provide_computational_units(self) -> Dict[str, Any]:
        """提供计算单元给 BrainCore。"""
        if self.model is None:
            raise RuntimeError("模型未初始化")

        return {
            "encode_text_mhc": self.model.encode_text,
            "model": self.model,
            "is_ready": lambda: self.model is not None,
            "config": self.config,
        }

    def setup_training(self, base_lr: float = 1e-4) -> MHCTrainer:
        """设置训练器。"""
        if self.model is None:
            raise RuntimeError("模型未初始化")

        mhc_config = MHCConfig(
            enable_mhc=True,
            projection_interval=self.config.projection_interval,
            sinkhorn_iterations=self.config.sinkhorn_iterations,
            sinkhorn_temperature=self.config.sinkhorn_temperature,
            residual_scale=self.config.mhc_residual_scale,
        )

        self.trainer = self.model.setup_training(base_lr, mhc_config)
        return self.trainer
