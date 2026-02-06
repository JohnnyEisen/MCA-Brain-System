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
    pass

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
ACTION_SIZE = 5     # 动作空间大小: [No_Op, Inject_Noise, Inject_Decoy, Mutate, Suppress]

class NeuralAdversaryEngine:
    """
    自适应场景生成引擎 (Adaptive Scenario Engine)
    根据当前环境自动切换：Torch (GPU/CPU) -> NumPy (Matrix Math) -> Random (Fallback)
    Used for generating complex test scenarios based on system state.
    """
    def __init__(self):
        self.backend = BACKEND
        self.weights = {}
        self.torch_model = None
        self.scenario_map = {
            "normal": 0, "oom": 1, "missing_dependency": 2, 
            "gl_error": 3, "mixin_conflict": 4, "version_conflict": 5, 
            "compound": 6, "adversarial": 7
        }
        
        print(f"[ScenarioEngine] Initializing backend... Type: [{self.backend.upper()}] - ({DEVICE_INFO})")
        
        if self.backend == "torch":
            self._init_torch()
        elif self.backend == "numpy":
            self._init_numpy()
        else:
            print("[ScenarioEngine] Info: Scientific libraries not found. Using heuristic fallback.")

    def _init_torch(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        class AdversaryNet(nn.Module):
            def __init__(self):
                super(AdversaryNet, self).__init__()
                self.fc1 = nn.Linear(INPUT_SIZE, HIDDEN_SIZE)
                self.fc2 = nn.Linear(HIDDEN_SIZE, HIDDEN_SIZE)
                self.fc3 = nn.Linear(HIDDEN_SIZE, ACTION_SIZE)
                self.dropout = nn.Dropout(0.2)
            def forward(self, x):
                x = F.relu(self.fc1(x))
                x = self.dropout(x)
                x = F.relu(self.fc2(x))
                return F.softmax(self.fc3(x), dim=1)
        
        # 安全加载模型，防止显存爆炸导致进程被 kill
        try:
             self.torch_model = AdversaryNet().to(self.device)
             self.torch_model.eval()
        except RuntimeError as e:
             print(f"[NeuralAdversary] 显存不足或 CUDA 错误，回退到 CPU: {e}")
             self.device = torch.device("cpu")
             self.torch_model = AdversaryNet().to(self.device)
             self.torch_model.eval()

    def _predict_torch(self, inputs):
        tensor_in = torch.tensor([inputs], dtype=torch.float32).to(self.device)
        with torch.no_grad():
            probs = self.torch_model(tensor_in)
            action = torch.multinomial(probs, 1).item()
        return action

    def _init_numpy(self):
        import numpy as np
        rng = np.random.default_rng()
        # He Initialization
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

    def _predict_numpy(self, inputs):
        import numpy as np
        x = np.array(inputs)
        # Forward pass (Manual)
        z1 = np.dot(x, self.weights['W1']) + self.weights['b1']
        a1 = self._relu(z1)
        z2 = np.dot(a1, self.weights['W2']) + self.weights['b2']
        a2 = self._relu(z2)
        z3 = np.dot(a2, self.weights['W3']) + self.weights['b3']
        probs = self._softmax(z3)
        action = np.random.choice(len(probs), p=probs)
        return action

    def decide_action(self, scenario: str, progress: float, phase_idx: int) -> int:
        # Global Aggression Control (Reduce spam)
        # 0.7 probability to do NOTHING (Force No-Op) regardless of NN output
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
        while len(inputs) < INPUT_SIZE: inputs.append(0.0)

        if self.backend == "torch":
            try: return self._predict_torch(inputs)
            except: return random.randint(0, ACTION_SIZE - 1)
        elif self.backend == "numpy":
            try: return self._predict_numpy(inputs)
            except: return random.randint(0, ACTION_SIZE - 1)
        else:
            # Dummy logic
            threshold = 0.8 if progress > 0.9 else 0.2
            if random.random() < threshold:
                return random.choice([1, 2])
            return 0

    def load(self, path="adversary_model.pth"):
        if self.backend == "torch" and os.path.exists(path):
            try:
                self.torch_model.load_state_dict(torch.load(path, map_location=self.device))
                print(f"[NeuralAdversary] Weights loaded: {path}")
            except: pass

    def save(self, path="adversary_model.pth"):
        if self.backend == "torch":
            torch.save(self.torch_model.state_dict(), path)

if __name__ == "__main__":
    agent = NeuralAdversaryEngine()
    print("Action test:", agent.decide_action("oom", 0.5, 1))
