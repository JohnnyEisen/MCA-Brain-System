"""Neural Workflow DLC: 训练/推理流水线管理。"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional
from pathlib import Path

from brain_system import BrainCore, BrainDLC, BrainDLCType, DLCManifest
from brain_system.security import SafeSerializer

class NeuralWorkflowDLC(BrainDLC):
    def get_manifest(self) -> DLCManifest:
        return DLCManifest(
            name="Neural Workflow Manager",
            version="1.1.0",
            author="Brain AI Systems",
            description="管理模型训练循环、检查点与推理流水线",
            dlc_type=BrainDLCType.MANAGER,
            dependencies=["Brain Core", "Neural Network Operators"],
            priority=30
        )

    def _initialize(self):
        self.active_trainings: Dict[str, Dict] = {}
        # 获取 NN 算子库能力
        self.nn_dlc = None
        try:
             self.nn_dlc = self.brain.dlcs.get("Neural Network Operators")
        except Exception:
             pass
        logging.info("NeuralWorkflowDLC 初始化完成")

    def provide_computational_units(self) -> Dict[str, Any]:
        return {
            "train": self.train_loop,
            "inference": self.inference,
            "save_checkpoint": self.save_checkpoint,
            "load_checkpoint": self.load_checkpoint,
        }

    def train_loop(self, model: Any, data_loader: Any, epochs: int = 1, lr: float = 0.01, loss_fn: Optional[Any] = None) -> Dict[str, Any]:
        """训练循环 (基于 Duck Type Autograd)。"""
        if not hasattr(model, "parameters") or not hasattr(model, "zero_grad"):
            logging.warning("模型必须具备 parameters() 和 zero_grad() 方法")
            return {"status": "failed", "reason": "invalid_model"}

        history = {"loss": []}
        start_time = time.time()

        # 尝试自动获取默认 Loss (MSE)
        if loss_fn is None and self.nn_dlc:
            try:
                units = self.nn_dlc.provide_computational_units()
                if "ops" in units and "mse_loss" in units["ops"]:
                    loss_fn = units["ops"]["mse_loss"]
            except Exception:
                pass

        for epoch in range(epochs):
            total_loss = 0.0
            steps = 0
            
            # 若 model 有 train() 切换模式
            if hasattr(model, "train"):
                model.train()

            for batch_x, batch_y in data_loader:
                # 1. 清空梯度
                model.zero_grad()
                
                # 2. 前向
                pred = model(batch_x)
                
                # 3. 计算 Loss
                if loss_fn:
                    loss = loss_fn(pred, batch_y)
                elif hasattr(model, "compute_loss"):
                    loss = model.compute_loss(pred, batch_y)
                else:
                    # Fallback tricky implementation (Squared Error)
                    # 依赖 TensorNode 重载了 __sub__ 和 __mul__
                    diff = pred - batch_y
                    loss = diff * diff 

                # 4. 反向
                if hasattr(loss, "backward"):
                    loss.backward()
                    
                # 5. 更新参数 (SGD)
                for param in model.parameters():
                    if param.grad is not None:
                        param.data -= lr * param.grad
                
                # 记录
                loss_val = 0.0
                if hasattr(loss, "data"):
                    # 尝试转 float (兼容 numpy/cupy)
                    d = loss.data
                    if hasattr(d, "item"):
                        loss_val = float(d.item())
                    elif hasattr(d, "sum"):
                         loss_val = float(d.sum())
                    else:
                        try:
                            loss_val = float(d)
                        except:
                            loss_val = 0.0
                total_loss += loss_val
                steps += 1
            
            avg_loss = total_loss / max(steps, 1)
            history["loss"].append(avg_loss)
            logging.info(f"Epoch {epoch+1}/{epochs} Loss={avg_loss:.4f}")

        return {
            "status": "completed",
            "epochs": epochs,
            "history": history,
            "duration": time.time() - start_time
        }

    def inference(self, model: Any, x: Any) -> Any:
        if hasattr(model, "eval"):
            model.eval()
        return model(x)

    def save_checkpoint(self, model: Any, path: str):
        params = {}
        if hasattr(model, "parameters"):
            # 简单序列化 parameter data
            # 真实场景应使用 state_dict
            try:
                params = [p.data for p in model.parameters()]
            except:
                params = []
        
        # 使用 Security 模块序列化
        data_bytes = SafeSerializer.serialize({"params": params}, format="pickle")
        Path(path).write_bytes(data_bytes)
        return path

    def load_checkpoint(self, model: Any, path: str):
        if not Path(path).exists():
            raise FileNotFoundError(path)
            
        raw = Path(path).read_bytes()
        ckpt = SafeSerializer.deserialize(raw, format="pickle")
        
        saved_params = ckpt.get("params", [])
        if hasattr(model, "parameters"):
            current_params = list(model.parameters())
            for p, saved in zip(current_params, saved_params):
                p.data = saved
        return model
