"""Neural Adversary Engine - 自适应场景生成引擎"""
from __future__ import annotations

import os
import random
import json
import time
import math

# =================================================================================
# 1. 硬件环境检测与后端选择 (Hardware Backend Detection)
# =================================================================================
BACKEND = "none"
DEVICE_INFO = "Unknown"

# 尝试加载 PyTorch (Tier 1)
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    BACKEND = "torch"
    DEVICE_INFO = "CUDA" if torch.cuda.is_available() else "CPU (Torch)"
except ImportError:
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]
    F = None  # type: ignore[assignment]

# 如果失败，尝试加载 NumPy (Tier 2)
if BACKEND == "none":
    try:
        import numpy as np
        BACKEND = "numpy"
        DEVICE_INFO = "CPU (NumPy)"
    except ImportError:
        BACKEND = "dummy"
        DEVICE_INFO = "CPU (Python Random)"

# =================================================================================
# 2. 神经网络配置 (Hyperparameters)
# =================================================================================
INPUT_SIZE = 16     # 输入特征维度
HIDDEN_SIZE = 64    # 隐藏层大小
ACTION_SIZE = 5     # 动作空间大小

class NeuralAdversaryEngine:
    """自适应场景生成引擎"""
    
    def __init__(self):
        self.backend = BACKEND
        self.weights: dict = {}
        self.torch_model = None
        self.scenario_map = {
            "normal": 0, "oom": 1, "missing_dependency": 2,
            "gl_error": 3, "mixin_conflict": 4, "version_conflict": 5,
            "compound": 6, "adversarial": 7
        }
        
        print(f"[ScenarioEngine] 初始化后端: [{self.backend.upper()}] - ({DEVICE_INFO})")
        
        if self.backend == "torch":
            self._init_torch()
        elif self.backend == "numpy":
            self._init_numpy()
        else:
            print("[ScenarioEngine] 提示: 没找到科学计算库。将使用启发式回退算法。")

    def _init_torch(self):
        import torch.nn as nn
        import torch.nn.functional as F
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")  # type: ignore[union-attr]
        
        class AdversaryNet(nn.Module):  # type: ignore[attr-defined]
            def __init__(self):
                super().__init__()
                self.fc1 = nn.Linear(INPUT_SIZE, HIDDEN_SIZE)
                self.fc2 = nn.Linear(HIDDEN_SIZE, HIDDEN_SIZE)
                self.fc3 = nn.Linear(HIDDEN_SIZE, ACTION_SIZE)
                self.dropout = nn.Dropout(0.2)
            
            def forward(self, x):
                x = F.relu(self.fc1(x))
                x = self.dropout(x)
                x = F.relu(self.fc2(x))
                return F.softmax(self.fc3(x), dim=1)
        
        try:
            self.torch_model = AdversaryNet().to(self.device)
            self.torch_model.eval()
        except RuntimeError as e:
            print(f"[NeuralAdversary] 显存不足，回退到 CPU: {e}")
            self.device = torch.device("cpu")
            self.torch_model = AdversaryNet().to(self.device)
            self.torch_model.eval()

    def _predict_torch(self, inputs) -> int:
        tensor_in = torch.tensor([inputs], dtype=torch.float32).to(self.device)  # type: ignore[union-attr]
        with torch.no_grad():  # type: ignore[union-attr]
            probs = self.torch_model(tensor_in)  # type: ignore[union-attr]
            action = torch.multinomial(probs, 1).item()  # type: ignore[union-attr]
        return action

    def _init_numpy(self):
        import numpy as np
        rng = np.random.default_rng()
        self.weights = {
            'W1': rng.standard_normal((INPUT_SIZE, HIDDEN_SIZE)) * np.sqrt(2/INPUT_SIZE),
            'b1': np.zeros(HIDDEN_SIZE),
            'W2': rng.standard_normal((HIDDEN_SIZE, HIDDEN_SIZE)) * np.sqrt(2/HIDDEN_SIZE),
            'b2': np.zeros(HIDDEN_SIZE),
            'W3': rng.standard_normal((HIDDEN_SIZE, ACTION_SIZE)) * np.sqrt(2/HIDDEN_SIZE),
            'b3': np.zeros(ACTION_SIZE)
        }

    def _relu(self, x):
        import numpy as np
        return np.maximum(0, x)

    def _softmax(self, x):
        import numpy as np
        e_x = np.exp(x - np.max(x))
        return e_x / e_x.sum()

    def _predict_numpy(self, inputs) -> int:
        import numpy as np
        x = np.array(inputs)
        z1 = np.dot(x, self.weights['W1']) + self.weights['b1']
        a1 = self._relu(z1)
        z2 = np.dot(a1, self.weights['W2']) + self.weights['b2']
        a2 = self._relu(z2)
        z3 = np.dot(a2, self.weights['W3']) + self.weights['b3']
        probs = self._softmax(z3)
        action = np.random.choice(len(probs), p=probs)
        return action

    def decide_action(self, scenario: str, progress: float, phase_idx: int) -> int:
        # 0.7 概率返回 0 (No-Op)
        if random.random() < 0.7:
            return 0

        sid = self.scenario_map.get(scenario, 0)
        inputs = [
            float(sid) / 10.0,
            progress,
            float(phase_idx) / 3.0,
            math.sin(progress * 3.14),
            random.random()
        ]
        while len(inputs) < INPUT_SIZE:
            inputs.append(0.0)

        if self.backend == "torch" and self.torch_model is not None:
            try:
                return self._predict_torch(inputs)
            except Exception:
                return random.randint(0, ACTION_SIZE - 1)
        elif self.backend == "numpy":
            try:
                return self._predict_numpy(inputs)
            except Exception:
                return random.randint(0, ACTION_SIZE - 1)
        else:
            threshold = 0.8 if progress > 0.9 else 0.2
            if random.random() < threshold:
                return random.choice([1, 2])
            return 0

    def load(self, path: str = "adversary_model.pth"):
        if self.backend == "torch" and self.torch_model is not None and os.path.exists(path):
            try:
                self.torch_model.load_state_dict(torch.load(path, map_location=self.device))  # type: ignore[union-attr]
                print(f"[NeuralAdversary] Weights loaded: {path}")
            except Exception as e:
                print(f"[NeuralAdversary] Failed to load weights: {e}")

    def save(self, path: str = "adversary_model.pth"):
        if self.backend == "torch" and self.torch_model is not None:
            torch.save(self.torch_model.state_dict(), path)  # type: ignore[union-attr]

if __name__ == "__main__":
    agent = NeuralAdversaryEngine()
    print("Action test:", agent.decide_action("oom", 0.5, 1))
