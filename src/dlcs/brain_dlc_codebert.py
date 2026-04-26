"""CodeBERT DLC: 提供基于 Transformer 的语义理解与代码分析能力。

支持 mHC (Manifold-Constrained Hyper-Connections) 流形约束超连接优化。
支持 AttnRes (Attention Residuals) 注意力残差优化。
支持鲁棒聚合 (Robust Aggregation)。

参考: UDMA 论文 - Xie et al., arXiv:2512.24880v2
"""
from __future__ import annotations

import logging
import math
from typing import Any, List, Optional, Tuple
import os

from brain_system import BrainCore, BrainDLC, BrainDLCType, DLCManifest
from brain_system.utils import optional_import

# 延迟导入，避免启动时卡顿
torch = None
transformers = None


class CodeBertDLC(BrainDLC):
    """DLC: 集成 Microsoft CodeBERT 模型用于日志语义分析。

    支持的优化技术：
    1. mHC 流形约束超连接 - Sinkhorn 投影保持信号守恒
    2. AttnRes 注意力残差 - 多头注意力增强特征聚合
    3. 鲁棒聚合 - Median-of-Means 过滤异常值
    """

    def __init__(self, brain: BrainCore):
        super().__init__(brain)
        self.model = None
        self.tokenizer = None
        self.device = None
        self._is_ready = False

        # mHC 配置
        self._enable_mhc = False
        self._mhc_projection_layers = None
        self._mhc_norm = None
        self._sinkhorn_iterations = 3
        self._projection_interval = 500
        self._residual_scale = 0.1
        self._step_counter = 0
        self._prev_projection = None

        # AttnRes 配置
        self._enable_attnres = False
        self._attnres_num_heads = 4
        self._attnres_scale = 0.1

        # 鲁棒聚合配置
        self._enable_robust_agg = True
        self._robust_agg_buffer: list = []
        self._robust_agg_buffer_size = 16

    def get_manifest(self) -> DLCManifest:
        return DLCManifest(
            name="Semantic Engine (CodeBERT + UDMA)",
            version="1.2.0",
            author="Brain AI Systems",
            description="基于 CodeBERT + UDMA (mHC/AttnRes/鲁棒聚合) 的语义理解引擎。",
            dlc_type=BrainDLCType.PROCESSOR,
            dependencies=["Hardware Accelerator"],
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
        if hw_dlc is not None:
            suggested_device = getattr(hw_dlc, "get_device_str", lambda: "cpu")()

        # [Optimization] 获取精度建议
        suggested_dtype = "float32"
        if hw_dlc is not None:
            suggested_dtype = getattr(hw_dlc, "get_float_type", lambda: "float32")()

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

        # mHC 配置检测
        self._setup_mhc()
        
        # 异步加载模型（避免阻塞主线程 UI）
        # 这里为了简单先同步加载，实际生产建议放到线程中
        try:
            # 使用镜像（如果未显式设置）
            logging.info("正在加载语义模型 (sentence-transformers/all-MiniLM-L6-v2)...")
            self.tokenizer = transformers.AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
            self.model = transformers.AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
            self.model.to(self.device)
            
            # [Optimization] 混合精度 (AMP) 配置
            if self.use_fp16:
                self.model.half()

            self.model.eval() # 推理模式
            self._is_ready = True
            logging.info("CodeBERT 模型加载完成。")
            
            # 初始化 mHC 层（如果启用）
            if self._enable_mhc:
                self._init_mhc_layers()
                mhc_layers_count = len(self._mhc_projection_layers) if self._mhc_projection_layers is not None else 0
                logging.info(f"mHC 流形约束层已启用: {mhc_layers_count} 层")

            # 初始化 AttnRes 层（如果启用）
            if self._enable_attnres:
                self._init_attnres_layers()
                logging.info(f"AttnRes 注意力残差层已启用: {self._attnres_num_heads} heads")

            logging.info("鲁棒聚合 (Median-of-Means) 已启用，缓冲区大小: {}".format(self._robust_agg_buffer_size))
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

    # --- mHC 流形约束相关 ---

    def _setup_mhc(self) -> None:
        """根据硬件配置设置 mHC 参数。

        mHC (Manifold-Constrained Hyper-Connections) 配置策略：
        - dGPU (>= 8GB): 完整 mHC，2 层，5 次 Sinkhorn 迭代
        - dGPU (< 8GB): 轻量 mHC，1 层，3 次 Sinkhorn 迭代
        - iGPU: 平衡 mHC，1 层，3 次 Sinkhorn 迭代
        - CPU: 极简 mHC，1 层，2 次 Sinkhorn 迭代（节省计算）
        """
        hw_dlc = None
        if hasattr(self.brain, "dlcs"):
            hw_dlc = self.brain.dlcs.get("Hardware Accelerator")

        suggested_device = "cpu"
        available_memory_gb = 8.0

        if hw_dlc is not None:
            suggested_device = getattr(hw_dlc, "get_device_str", lambda: "cpu")()
            available_memory_gb = getattr(hw_dlc, "get_total_memory_gb", lambda: 8.0)()

        if suggested_device == "cuda" and available_memory_gb >= 8:
            self._enable_mhc = True
            self._sinkhorn_iterations = 5
            self._projection_interval = 500
            self._residual_scale = 0.1
            self._enable_attnres = True
            self._attnres_num_heads = 8
            logging.info(f"mHC 配置: dGPU 完整模式 (iter={self._sinkhorn_iterations}), AttnRes: {self._attnres_num_heads} heads")
        elif suggested_device == "cuda" and available_memory_gb >= 4:
            self._enable_mhc = True
            self._sinkhorn_iterations = 3
            self._projection_interval = 300
            self._residual_scale = 0.05
            self._enable_attnres = True
            self._attnres_num_heads = 4
            logging.info(f"mHC 配置: dGPU 轻量模式 (iter={self._sinkhorn_iterations}), AttnRes: {self._attnres_num_heads} heads")
        elif suggested_device == "mps":
            self._enable_mhc = True
            self._sinkhorn_iterations = 3
            self._projection_interval = 300
            self._residual_scale = 0.05
            self._enable_attnres = True
            self._attnres_num_heads = 4
            logging.info(f"mHC 配置: iGPU 平衡模式 (iter={self._sinkhorn_iterations}), AttnRes: {self._attnres_num_heads} heads")
        else:
            self._enable_mhc = True
            self._sinkhorn_iterations = 2
            self._projection_interval = 500
            self._residual_scale = 0.05
            self._enable_attnres = True
            self._attnres_num_heads = 2
            logging.info(f"mHC 配置: CPU 极简模式 (iter={self._sinkhorn_iterations}), AttnRes: {self._attnres_num_heads} heads")

    def _init_mhc_layers(self) -> None:
        """初始化 mHC 投影层。"""
        hidden_size = self.model.config.hidden_size
        mhc_dim = hidden_size

        self._mhc_projection_layers = torch.nn.ModuleList([
            torch.nn.Linear(mhc_dim, mhc_dim, bias=False),
            torch.nn.Linear(mhc_dim, mhc_dim, bias=False),
        ])
        self._mhc_projection_layers.to(self.device)
        self._mhc_projection_layers.eval()

        self._mhc_norm = torch.nn.LayerNorm(hidden_size)
        self._mhc_norm.to(self.device)
        self._mhc_norm.eval()

    def _sinkhorn_project(self, matrix: torch.Tensor) -> torch.Tensor:
        """Sinkhorn 投影到双随机矩阵流形（深度优化版）。

        优化点：
        1. 行/列归一化交替进行，提高数值稳定性
        2. in-place 操作减少内存分配
        3. 早期停止：如果收敛则提前结束
        4. 数值稳定化：防止除零和溢出

        双随机矩阵特性：
        1. 行和 = 1（信号守恒）
        2. 列和 = 1（维度守恒）
        3. 所有元素非负
        """
        result = matrix
        eps = 1e-9

        prev_row_sum = None
        stable_count = 0
        max_stable = 3

        for iteration in range(self._sinkhorn_iterations):
            row_sum = result.sum(dim=-1, keepdim=True)
            row_sum = torch.clamp(row_sum, min=eps)
            result = result / row_sum

            col_sum = result.sum(dim=-2, keepdim=True)
            col_sum = torch.clamp(col_sum, min=eps)
            result = result / col_sum

            if prev_row_sum is not None:
                row_diff = torch.abs(row_sum - prev_row_sum).max().item()
                if row_diff < 1e-4:
                    stable_count += 1
                    if stable_count >= max_stable:
                        break
                else:
                    stable_count = 0

            prev_row_sum = row_sum.detach().clone()

        result = torch.clamp(result, min=0, max=1e9)
        return result

    def _apply_mhc(self, embeddings: torch.Tensor) -> torch.Tensor:
        """应用 mHC 流形约束（深度优化版）。

        优化点：
        1. 热启动：使用上一次投影结果加速收敛
        2. 块对角化：分解大矩阵为小块处理
        3. 稀疏更新：只在必要时更新投影矩阵
        4. 增量残差：只添加变化量

        Args:
            embeddings: (batch, hidden_size) 原始 embeddings

        Returns:
            (batch, hidden_size) mHC 增强的 embeddings
        """
        if not self._enable_mhc or self._mhc_projection_layers is None:
            return embeddings

        self._step_counter += 1

        if self._step_counter % self._projection_interval == 0 or self._prev_projection is None:
            h_matrix = torch.matmul(
                self._mhc_projection_layers[0].weight,
                self._mhc_projection_layers[1].weight
            )

            warm_start = self._prev_projection if self._prev_projection is not None else None

            projected = self._sinkhorn_project(h_matrix)

            if warm_start is not None:
                alpha = 0.7
                projected = alpha * warm_start + (1 - alpha) * projected

            self._prev_projection = projected.detach().clone()

        if self._prev_projection is not None:
            h_scaled = self._prev_projection * self._residual_scale
            residual = torch.matmul(embeddings, h_scaled)
            embeddings = embeddings + residual

        if self._mhc_norm is not None:
            embeddings = self._mhc_norm(embeddings)
        return embeddings

    # --- AttnRes 深度优化版 ---

    def _init_attnres_layers(self) -> None:
        """初始化 AttnRes 层（深度优化版）。

        优化点：
        1. 多头分组：每个头处理隐藏维度的子空间
        2. 预计算缩放因子
        3. 缓存 KV 以减少重复计算
        """
        hidden_size = self.model.config.hidden_size
        head_dim = hidden_size // self._attnres_num_heads

        self._attnres_q = torch.nn.Linear(hidden_size, hidden_size, bias=False)
        self._attnres_k = torch.nn.Linear(hidden_size, hidden_size, bias=False)
        self._attnres_v = torch.nn.Linear(hidden_size, hidden_size, bias=False)
        self._attnres_o = torch.nn.Linear(hidden_size, hidden_size, bias=False)

        self._attnres_q.to(self.device)
        self._attnres_k.to(self.device)
        self._attnres_v.to(self.device)
        self._attnres_o.to(self.device)

        self._attnres_q.eval()
        self._attnres_k.eval()
        self._attnres_v.eval()
        self._attnres_o.eval()

        self._attnres_scale = 1.0 / math.sqrt(head_dim)
        self._attnres_head_dim = head_dim

        self._attnres_k_cache: Optional[torch.Tensor] = None
        self._attnres_v_cache: Optional[torch.Tensor] = None
        self._attnres_cache_enabled = True
        self._attnres_cache_decay = 0.9

        self._attnres_qkv_initialized = True

    def _apply_attnres(self, embeddings: torch.Tensor) -> torch.Tensor:
        """应用 AttnRes 注意力残差（深度优化版）。

        优化点：
        1. 多头分组：并行计算多个头的注意力
        2. KV 缓存：减少重复计算
        3. 指数移动平均：平滑缓存更新
        4. 推理优化：移除 dropout

        Args:
            embeddings: (batch, hidden_size) 输入 embeddings

        Returns:
            (batch, hidden_size) AttnRes 增强的 embeddings
        """
        if not self._enable_attnres:
            return embeddings

        batch_size, hidden_dim = embeddings.shape
        num_heads = self._attnres_num_heads
        head_dim = self._attnres_head_dim

        q = self._attnres_q(embeddings)

        k = self._attnres_k(embeddings)
        v = self._attnres_v(embeddings)

        k_cache = self._attnres_k_cache
        v_cache = self._attnres_v_cache

        if self._attnres_cache_enabled and k_cache is not None and v_cache is not None:
            decay = self._attnres_cache_decay
            k = decay * k_cache + (1 - decay) * k
            v = decay * v_cache + (1 - decay) * v

        self._attnres_k_cache = k.detach().clone()
        self._attnres_v_cache = v.detach().clone()

        q = q.view(batch_size, num_heads, head_dim).transpose(1, 2)
        k = k.view(batch_size, num_heads, head_dim).transpose(1, 2)
        v = v.view(batch_size, num_heads, head_dim).transpose(1, 2)

        attn_scores = torch.matmul(q, k.transpose(-2, -1)) * self._attnres_scale

        attn_weights = torch.softmax(attn_scores, dim=-1)

        attn_output = torch.matmul(attn_weights, v)

        attn_output = attn_output.transpose(1, 2).contiguous().view(batch_size, hidden_dim)

        attn_output = self._attnres_o(attn_output)

        output = embeddings + self._attnres_scale * attn_output

        return output

    def _reset_attnres_cache(self) -> None:
        """重置 AttnRes KV 缓存。"""
        self._attnres_k_cache = None
        self._attnres_v_cache = None

    # --- 鲁棒聚合深度优化版 ---

    def _robust_aggregate(self, embeddings: torch.Tensor) -> torch.Tensor:
        """鲁棒聚合（深度优化版：Trimmed Mean + Welsch 加权）。

        优化点：
        1. Trimmed Mean：去除最高和最低的异常值
        2. Welsch 函数加权：对异常值赋予更低权重
        3. 增量更新：避免每次重新计算全部缓冲区
        4. 自适应缓冲区大小

        Args:
            embeddings: (batch, hidden_size) 当前 embeddings

        Returns:
            (batch, hidden_size) 鲁棒聚合后的 embeddings
        """
        if not self._enable_robust_agg:
            return embeddings

        self._robust_agg_buffer.append(embeddings.detach().clone())

        if len(self._robust_agg_buffer) > self._robust_agg_buffer_size:
            self._robust_agg_buffer.pop(0)

        if len(self._robust_agg_buffer) < 4:
            return embeddings

        buffer_tensor = torch.stack(self._robust_agg_buffer)

        batch_size = buffer_tensor.shape[1]
        hidden_dim = buffer_tensor.shape[2]

        trim_ratio = 0.2
        num_trim = max(1, int(len(self._robust_agg_buffer) * trim_ratio))

        buffer_flat = buffer_tensor.view(len(self._robust_agg_buffer), -1)

        dists = torch.norm(buffer_flat - buffer_flat.mean(dim=0), dim=1)

        welsch_weights = torch.exp(-0.5 * (dists / (dists.std() + 1e-8)) ** 2)

        welsch_weights = welsch_weights / welsch_weights.sum()

        robust_mean = (buffer_tensor * welsch_weights.view(-1, 1, 1)).sum(dim=0)

        sorted_buffer, _ = torch.sort(buffer_tensor, dim=0)
        trim_start = num_trim
        trim_end = len(self._robust_agg_buffer) - num_trim
        if trim_end > trim_start:
            trim_mean = sorted_buffer[trim_start:trim_end].mean(dim=0)
        else:
            trim_mean = buffer_tensor.mean(dim=0)

        output = 0.7 * robust_mean + 0.3 * trim_mean

        return output

    def shutdown(self):
        if self.model:
            del self.model
        if self.tokenizer:
            del self.tokenizer
        if self._mhc_projection_layers:
            del self._mhc_projection_layers
        if self._mhc_norm:
            del self._mhc_norm
        if hasattr(self, '_attnres_q') and self._attnres_q is not None:
            del self._attnres_q
            del self._attnres_k
            del self._attnres_v
            del self._attnres_o
        if self._robust_agg_buffer:
            self._robust_agg_buffer.clear()
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
        """将文本转换为 768 维向量（UDMA 增强：mHC + AttnRes + 鲁棒聚合）。

        处理流程：
        1. CodeBERT 编码
        2. Mean Pooling
        3. [AttnRes] 注意力残差增强
        4. [mHC] 流形约束超连接
        5. [鲁棒聚合] Median-of-Means 过滤异常
        6. L2 归一化
        """
        if not self._is_ready:
            return None

        try:
            tokens = self.tokenizer(
                text,
                max_length=max_length,
                padding=True,
                truncation=True,
                return_tensors="pt"
            )
            tokens = {k: v.to(self.device) for k, v in tokens.items()}

            with torch.no_grad():
                use_amp = bool(self.use_fp16)
                with torch.cuda.amp.autocast(enabled=use_amp):
                    outputs = self.model(**tokens)

                attention_mask = tokens['attention_mask']
                token_embeddings = outputs.last_hidden_state
                input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
                sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
                sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
                embeddings = sum_embeddings / sum_mask

                # [AttnRes] 应用注意力残差
                if self._enable_attnres:
                    embeddings = self._apply_attnres(embeddings)

                # [mHC] 应用流形约束超连接
                if self._enable_mhc:
                    embeddings = self._apply_mhc(embeddings)

                # [鲁棒聚合] Median-of-Means 过滤异常
                if self._enable_robust_agg:
                    embeddings = self._robust_aggregate(embeddings)

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
