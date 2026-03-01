"""CodeBERT DLC: 提供基于 Transformer 的语义理解与代码分析能力。"""
from __future__ import annotations

import logging
from typing import Any, List, Optional
import os

from brain_system import BrainCore, BrainDLC, BrainDLCType, DLCManifest
from brain_system.utils import optional_import

# 延迟导入，避免启动时卡顿
torch = None
transformers = None

class CodeBertDLC(BrainDLC):
    """DLC: 集成 Microsoft CodeBERT 模型用于日志语义分析。"""

    def __init__(self, brain: BrainCore):
        super().__init__(brain)
        self.model = None
        self.tokenizer = None
        self.device = None
        self._is_ready = False

    def get_manifest(self) -> DLCManifest:
        return DLCManifest(
            name="Semantic Engine (CodeBERT)",
            version="1.0.0",
            author="Brain AI Systems",
            description="基于 CodeBERT 的语义理解引擎，提供高精度日志相似度匹配。",
            dlc_type=BrainDLCType.PROCESSOR,
            dependencies=["Hardware Accelerator"],  # 依赖硬件加速
            priority=50
        )

    def _initialize(self):
        global torch, transformers
        try:
            # 在导入 transformers 之前设置镜像环境变量
            if not os.environ.get("HF_ENDPOINT"):
                os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
                logging.info("已设置 HF_ENDPOINT=https://hf-mirror.com")

            # --- 屏蔽 httpx 和 transformers 的啰嗦日志 ---
            # 原因：transformers 会探测分片索引(index.json)，对单文件模型(如codebert)必然返回404，这是正常探测。
            # 为防止误解为错误，提高 httpx/transformers 的日志级别仅显示警告。
            logging.getLogger("httpx").setLevel(logging.WARNING)
            logging.getLogger("transformers").setLevel(logging.WARNING)
            logging.getLogger("huggingface_hub").setLevel(logging.WARNING)

            import importlib
            try:
                torch = importlib.import_module("torch")
            except Exception as e:
                logging.error(f"torch 导入失败: {e}")
                raise
            try:
                transformers = importlib.import_module("transformers")
            except Exception as e:
                logging.error(f"transformers 导入失败: {e}")
                raise
        except Exception as e:
            raise ImportError(f"缺少 torch 或 transformers 库，或依赖导入失败: {e}")

        # 获取硬件加速提供的设备
        hw_dlc = None
        if hasattr(self.brain, "dlcs"):
            hw_dlc = self.brain.dlcs.get("Hardware Accelerator")
        
        suggested_device = "cpu"
        if hw_dlc and hasattr(hw_dlc, "get_device_str"):
            suggested_device = hw_dlc.get_device_str()
        
        # [Optimization] 获取精度建议
        suggested_dtype = "float32"
        if hw_dlc and hasattr(hw_dlc, "get_float_type"):
            suggested_dtype = hw_dlc.get_float_type()

        # 最终决策：必须 Torch 也支持才行
        if suggested_device == "cuda" and not torch.cuda.is_available():
            logging.warning("Hardware DLC 检测到了 GPU，但 PyTorch 未检测到 CUDA 支持。模型将回退到 CPU 运行。")
            logging.warning("可能原因: 安装了 CPU 版 PyTorch 或 CUDA 驱动版本不匹配。")
            device_str = "cpu"
        elif suggested_device == "cuda":
            device_str = "cuda"
        else:
            device_str = "cuda" if torch.cuda.is_available() else "cpu"
        
        self.device = torch.device(device_str)
        self.use_fp16 = (suggested_dtype == "float16" and device_str == "cuda")
        logging.info(f"CodeBERT 引擎运行配置: 设备={self.device}, 精度={'FP16 (混合精度 AMP)' if self.use_fp16 else 'FP32'}")

        # 异步加载模型（避免阻塞主线程 UI）
        # 这里为了简单先同步加载，实际生产建议放到线程中
        try:
            # 使用镜像（如果未显式设置）
            logging.info("正在加载语义模型 (sentence-transformers/all-MiniLM-L6-v2)...")
            self.tokenizer = transformers.AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
            self.model = transformers.AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
            self.model.to(self.device)
            
            # [Optimization] 混合精度 (AMP) 配置
            # 用户选择 "同时使用" (FP16 + FP32):
            # 1. 权重保持 FP32 (高精度存储，避免下溢)
            # 2. 计算使用 FP16 (高吞吐，通过 autocast 自动降级)
            # 注意: 如果可以容忍极微小的精度损失以换取减半的显存占用，可恢复 .half() 调用
            # if self.use_fp16:
            #     self.model.half()

            self.model.eval() # 推理模式
            self._is_ready = True
            logging.info("CodeBERT 模型加载完成。")
        except Exception as e:
            # SSL 证书异常时尝试禁用验证（仅作为最后兜底）
            if "CERTIFICATE_VERIFY_FAILED" in str(e) and not os.environ.get("HF_HUB_DISABLE_SSL_VERIFICATION"):
                os.environ["HF_HUB_DISABLE_SSL_VERIFICATION"] = "1"
                logging.warning("检测到 SSL 证书错误，已临时禁用 HF SSL 验证并重试一次")
                try:
                    self.tokenizer = transformers.AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
                    self.model = transformers.AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
                    self.model.to(self.device)
                    self.model.eval()
                    self._is_ready = True
                    logging.info("CodeBERT 模型加载完成。")
                    return
                except Exception as e2:
                    raise RuntimeError(f"模型下载或加载失败: {e2}")

            raise RuntimeError(f"模型下载或加载失败: {e}")

    def shutdown(self):
        if self.model:
            del self.model
        if self.tokenizer:
            del self.tokenizer
        if torch and torch.cuda.is_available():
            torch.cuda.empty_cache()

    def provide_computational_units(self) -> dict[str, Any]:
        return {
            "encode_text": self.encode_text,
            "calculate_similarity": self.calculate_similarity,
            "is_ready": lambda: self._is_ready
        }

    # --- 核心功能 ---

    def encode_text(self, text: str, max_length: int = 510) -> Optional[List[float]]:
        """将文本转换为 768 维向量。"""
        if not self._is_ready:
            return None
        
        try:
            # 截断策略：保留头尾（因为 Crash Log 通常头尾重要）
            # 这里简化处理，直接截断
            tokens = self.tokenizer(
                text, 
                max_length=max_length, 
                padding=True, 
                truncation=True, 
                return_tensors="pt"
            )
            tokens = {k: v.to(self.device) for k, v in tokens.items()}
            
            with torch.no_grad():
                # [Optimization] 开启混合精度上下文 (AMP)
                # 这会自动在 FP16 (计算快) 和 FP32 (累加准) 之间切换
                with torch.cuda.amp.autocast(enabled=self.use_fp16):
                    outputs = self.model(**tokens)
                
                # [Optimization] Mean Pooling 配合 L2 归一化解决各向异性问题
                attention_mask = tokens['attention_mask']
                token_embeddings = outputs.last_hidden_state
                input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
                sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
                sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
                embeddings = sum_embeddings / sum_mask
                
                # L2 归一化
                embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
                
            return embeddings.cpu().numpy()[0].tolist()
        except Exception as e:
            logging.error(f"Embedding 生成失败: {e}")
            return None

    def calculate_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度。"""
        if not vec1 or not vec2:
            return 0.0
        
        # 使用 torch 计算更高效
        try:
            t1 = torch.tensor(vec1, device=self.device)
            t2 = torch.tensor(vec2, device=self.device)
            return torch.nn.functional.cosine_similarity(t1.unsqueeze(0), t2.unsqueeze(0)).item()
        except Exception:
            return 0.0
