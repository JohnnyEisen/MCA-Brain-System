"""
mHC 模型训练脚本

用法:
    python train_mhc.py --preset balanced
    python train_mhc.py --config my_config.json
    python train_mhc.py --base-model sentence-transformers/all-MiniLM-L6-v2 --epochs 5

参考: UDMA 论文 - Xie et al., arXiv:2512.24880v2
"""
from __future__ import annotations

import os
import sys
import logging
import random
from pathlib import Path
from typing import Optional, List, Dict, Any

import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dlcs.mhc_codebert import MHCCodeBert, MHCCodeBertConfig
from dlcs.mhc_config import TrainingConfig, parse_args, get_preset, PRESET_CONFIGS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CrashLogDataset(Dataset):
    """崩溃日志数据集。

    实际应用中应从文件加载真实数据。
    """

    def __init__(
        self,
        texts: List[str],
        labels: Optional[List[int]] = None,
        max_length: int = 512,
    ):
        """
        Args:
            texts: 日志文本列表
            labels: 标签列表（可选）
            max_length: 最大长度
        """
        self.texts = texts
        self.labels = labels or [0] * len(texts)
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        return {
            "text": self.texts[idx],
            "label": self.labels[idx],
        }


class MHCTrainer:
    """简化的 mHC 训练循环。"""

    def __init__(
        self,
        model: MHCCodeBert,
        config: TrainingConfig,
        output_dir: str,
    ):
        """
        Args:
            model: mHC 模型
            config: 训练配置
            output_dir: 输出目录
        """
        self.model = model
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.device = torch.device(config.device if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

        self.optimizer = torch.optim.AdamW(
            filter(lambda p: p.requires_grad, model.parameters()),
            lr=config.base_lr,
            weight_decay=0.01,
        )

        self.scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer,
            T_max=config.num_epochs * 100,
        )

        self.global_step = 0
        self.best_loss = float("inf")

    def train_epoch(self, dataloader: DataLoader) -> float:
        """训练一个 epoch。"""
        self.model.train()
        total_loss = 0.0
        num_batches = 0

        for batch in dataloader:
            texts = batch["text"]
            labels = batch["label"]

            embeddings = []
            for text in texts:
                emb = self.model.encode_text(text)
                if emb is not None:
                    embeddings.append(emb)
                else:
                    embeddings.append([0.0] * self.model.get_embedding_dim())

            embeddings_tensor = torch.tensor(embeddings, device=self.device)
            labels_tensor = torch.tensor(labels, device=self.device)

            logits = self.model.classifier(embeddings_tensor)

            loss = torch.nn.functional.cross_entropy(logits, labels_tensor)

            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
            self.optimizer.step()
            self.scheduler.step()

            total_loss += loss.item()
            num_batches += 1
            self.global_step += 1

            if self.global_step % self.config.log_interval == 0:
                logger.info(
                    f"Step {self.global_step} | Loss: {loss.item():.4f} | "
                    f"LR: {self.scheduler.get_last_lr()[0]:.2e}"
                )

        return total_loss / max(num_batches, 1)

    def train(self, train_dataset: Dataset, val_dataset: Optional[Dataset] = None) -> Dict[str, List[float]]:
        """执行完整训练。"""
        train_loader = DataLoader(
            train_dataset,
            batch_size=self.config.batch_size,
            shuffle=True,
            num_workers=0,
        )

        history = {"train_loss": []}

        for epoch in range(self.config.num_epochs):
            logger.info(f"\n=== Epoch {epoch + 1}/{self.config.num_epochs} ===")

            train_loss = self.train_epoch(train_loader)
            history["train_loss"].append(train_loss)

            logger.info(f"Epoch {epoch + 1} | Train Loss: {train_loss:.4f}")

            if train_loss < self.best_loss:
                self.best_loss = train_loss
                self.save_checkpoint("best_model.pt")
                logger.info(f"保存最佳模型 (loss={train_loss:.4f})")

            if (epoch + 1) % max(1, self.config.num_epochs // 3) == 0:
                self.save_checkpoint(f"checkpoint_epoch_{epoch + 1}.pt")

        self.save_checkpoint("final_model.pt")
        logger.info("训练完成!")

        return history

    def save_checkpoint(self, filename: str) -> None:
        """保存检查点。"""
        path = self.output_dir / filename
        torch.save(
            {
                "model_state": self.model.state_dict(),
                "optimizer_state": self.optimizer.state_dict(),
                "scheduler_state": self.scheduler.state_dict(),
                "global_step": self.global_step,
                "best_loss": self.best_loss,
                "config": self.config,
            },
            path,
        )
        logger.debug(f"检查点已保存: {path}")

    @classmethod
    def load_checkpoint(cls, path: str, model: MHCCodeBert, config: TrainingConfig) -> "MHCTrainer":
        """加载检查点。"""
        checkpoint = torch.load(path, map_location="cpu")
        trainer = cls(model, config, os.path.dirname(path))
        trainer.model.load_state_dict(checkpoint["model_state"])
        trainer.optimizer.load_state_dict(checkpoint["optimizer_state"])
        trainer.scheduler.load_state_dict(checkpoint["scheduler_state"])
        trainer.global_step = checkpoint["global_step"]
        trainer.best_loss = checkpoint["best_loss"]
        return trainer


def create_demo_dataset() -> CrashLogDataset:
    """创建演示数据集。

    实际应用中应从文件加载真实数据。
    """
    sample_texts = [
        "java.lang.NullPointerException: Cannot invoke method on null object",
        "Mixin injection failed: Critical injection failure in method",
        "net.minecraft.client.renderer.Tessellator: BufferBuilder error",
        "org.lwjgl.glfw.GLFW: GLFW error 65537",
        "java.lang.OutOfMemoryError: Java heap space",
        "java.lang.ClassNotFoundException: net.minecraft.entity.Entity",
        "FATAL: Server Hang Watchdog detected timeout",
        "TPS: 8.2 | Mean tick time: 312ms",
        "Entity count: 4523 | TileEntity count: 8932",
        "Mixin 'XYZ' in 'modid' failed to apply",
    ]

    labels = [0, 0, 0, 0, 0, 0, 1, 1, 1, 0]

    texts = sample_texts * 10

    return CrashLogDataset(texts, labels)


def main():
    """主函数。"""
    logger.info("=" * 60)
    logger.info("mHC Model Training - UDMA Implementation")
    logger.info("=" * 60)

    config = parse_args()

    logger.info(f"使用配置:")
    logger.info(f"  - 基础模型: {config.model.base_model}")
    logger.info(f"  - 启用 mHC: {config.model.enable_mhc}")
    logger.info(f"  - mHC 残差块数: {config.model.num_mhc_blocks}")
    logger.info(f"  - 投影间隔: {config.model.projection_interval}")
    logger.info(f"  - Sinkhorn 迭代: {config.model.sinkhorn_iterations}")
    logger.info(f"  - 批次大小: {config.batch_size}")
    logger.info(f"  - 训练轮数: {config.num_epochs}")
    logger.info(f"  - 设备: {config.device}")

    if not torch.cuda.is_available() and config.device == "cuda":
        logger.warning("CUDA 不可用，回退到 CPU")
        config.device = "cpu"

    torch.manual_seed(config.seed)
    random.seed(config.seed)
    np.random.seed(config.seed)

    logger.info("\n初始化 MHCCodeBert 模型...")
    mhc_config = MHCCodeBertConfig(
        base_model=config.model.base_model,
        enable_mhc=config.model.enable_mhc,
        mhc_residual_scale=config.model.mhc_residual_scale,
        mhc_hidden_ratio=config.model.mhc_hidden_ratio,
        sinkhorn_iterations=config.model.sinkhorn_iterations,
        sinkhorn_temperature=config.model.sinkhorn_temperature,
        projection_interval=config.model.projection_interval,
        num_mhc_blocks=config.model.num_mhc_blocks,
        mhc_dropout=config.model.mhc_dropout,
        trainable=True,
    )

    model = MHCCodeBert(mhc_config)
    model.freeze_base_model()
    model.enable_mhc_training()

    logger.info("\n准备训练数据...")
    train_dataset = create_demo_dataset()
    logger.info(f"训练样本数: {len(train_dataset)}")

    logger.info("\n开始训练...")
    trainer = MHCTrainer(model, config, config.output_dir)

    history = trainer.train(train_dataset)

    logger.info("\n训练完成!")
    logger.info(f"模型保存在: {config.output_dir}")


if __name__ == "__main__":
    main()
