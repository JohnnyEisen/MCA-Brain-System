"""Neural Network DLC: 算子与自动微分。"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Sequence
import collections

from brain_system import BrainCore, BrainDLC, BrainDLCType, DLCManifest
from brain_system.utils import optional_import

# 辅助类：Autograd 节点
class TensorNode:
    """包装数据与梯度信息。"""
    def __init__(self, data: Any, requires_grad: bool = False, creator: Optional['Function'] = None):
        self.data = data
        self.grad: Any = None
        self.requires_grad = requires_grad
        self.creator = creator
        self.generation = 0 if creator is None else creator.generation + 1

    def backward(self, grad: Any = None):
        if not self.requires_grad:
            return

        if grad is None:
            # 默认梯度为 1.0 (shape 同 data)
            xp = self._get_array_module(self.data)
            grad = xp.ones_like(self.data)

        # 累积当前梯度
        if self.grad is None:
            self.grad = grad
        else:
            self.grad += grad

        # 传递给 creator
        if self.creator:
            self.creator.backward(self.grad)

    def _get_array_module(self, x):
        # 更强健的 numpy / cupy 判别
        try:
            cp = optional_import("cupy")
            if cp and isinstance(x, cp.ndarray):
                return cp
        except Exception:
            pass
        return optional_import("numpy")

    def __add__(self, other):
        if not isinstance(other, TensorNode):
            other = TensorNode(other)
        return Add()(self, other)
    
    def __sub__(self, other):
        if not isinstance(other, TensorNode):
            other = TensorNode(other)
        return Sub()(self, other)

    def __mul__(self, other):
        if not isinstance(other, TensorNode):
            other = TensorNode(other)
        return Mul()(self, other)

    def __matmul__(self, other):
        if not isinstance(other, TensorNode):
            other = TensorNode(other)
        return MatMul()(self, other)

    def __repr__(self):
        return f"Tensor(shape={self.data.shape if hasattr(self.data, 'shape') else 'scalar'}, requires_grad={self.requires_grad})"


class Function:
    """可微分算子基类。"""
    def __init__(self):
        self.inputs: List[TensorNode] = []
        self.outputs: List[TensorNode] = []
        self.generation = 0

    def __call__(self, *inputs: TensorNode) -> TensorNode:
        self.inputs = inputs
        self.generation = max((x.generation for x in inputs), default=0)
        
        # Unpack data
        raw_inputs = [x.data for x in inputs]
        
        # Forward
        raw_outputs = self.forward(*raw_inputs)
        if not isinstance(raw_outputs, tuple):
            raw_outputs = (raw_outputs,)
        
        # Pack Output
        outputs = []
        requires_grad = any(x.requires_grad for x in inputs)
        for d in raw_outputs:
            out_node = TensorNode(d, requires_grad=requires_grad, creator=self if requires_grad else None)
            outputs.append(out_node)
        
        self.outputs = outputs
        return outputs[0] if len(outputs) == 1 else tuple(outputs)

    def forward(self, *args):
        raise NotImplementedError

    def backward(self, grad_output):
        # 计算输入梯度
        grad_inputs = self.backward_impl(grad_output)
        if not isinstance(grad_inputs, tuple):
            grad_inputs = (grad_inputs,)
        
        # 分发到各输入
        for x, g in zip(self.inputs, grad_inputs):
            if x.requires_grad:
                x.backward(g)

    def backward_impl(self, grad_output):
        raise NotImplementedError


# --- 具体算子实现 ---

class Add(Function):
    def forward(self, x0, x1):
        return x0 + x1
    
    def backward_impl(self, gy):
        return gy, gy

class Sub(Function):
    def forward(self, x0, x1):
        return x0 - x1
    
    def backward_impl(self, gy):
        return gy, -gy

class Mul(Function):
    def forward(self, x0, x1):
        self.x0 = x0
        self.x1 = x1
        return x0 * x1
    
    def backward_impl(self, gy):
        return gy * self.x1, gy * self.x0

class MatMul(Function):
    def forward(self, x, W):
        self.x = x
        self.W = W
        return x @ W
    
    def backward_impl(self, gy):
        # x: (N, D), W: (D, H) -> out: (N, H)
        # gx: (N, D) = gy @ W.T
        # gW: (D, H) = x.T @ gy
        return gy @ self.W.T, self.x.T @ gy

class Relu(Function):
    def forward(self, x):
        self.mask = (x > 0)
        return x * self.mask
    
    def backward_impl(self, gy):
        return gy * self.mask

class MSELoss(Function):
    def forward(self, pred, target):
        self.diff = pred - target
        self.N = pred.size
        return (self.diff ** 2).sum() / self.N
    
    def backward_impl(self, gy):
        return gy * 2 * self.diff / self.N, -gy * 2 * self.diff / self.N


# DLC 定义

class NeuralNetworkOperatorsDLC(BrainDLC):
    def get_manifest(self) -> DLCManifest:
        return DLCManifest(
            name="Neural Network Operators",
            version="1.1.0",
            author="Brain AI Systems",
            description="提供基础神经网络算子与简易 Autograd",
            dlc_type=BrainDLCType.PROCESSOR,
            dependencies=["Brain Core", "Hardware Accelerator"],
            priority=20
        )

    def _initialize(self):
        # 检查 numpy
        self.np = optional_import("numpy")
        if self.np is None:
            logging.warning("NeuralNetworkOperatorsDLC: 缺少 numpy，无法工作")
            return

        # 获取 Hardware DLC (如果需要)
        self.hw_dlc = None
        try:
             self.hw_dlc = self.brain.dlcs.get("Hardware Accelerator")
        except Exception:
             pass

        logging.info("NeuralNetworkOperatorsDLC 已就绪")

    def provide_computational_units(self) -> Dict[str, Any]:
        return {
            "Tensor": TensorNode,
            "Function": Function,
            "ops": {
                "add": Add(),
                "sub": Sub(),
                "mul": Mul(),
                "matmul": MatMul(),
                "relu": Relu(),
                "mse_loss": MSELoss(),
            }
        }
