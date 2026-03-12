import pytest
from unittest.mock import MagicMock
import sys
import os

# Ensure dlc imports work by adding root to path if needed, 
# though usually pytest handles this relative to root.

from brain_system.dlc import BrainDLC
from dlcs.brain_dlc_distributed import DistributedComputingDLC


class MockBrainCore:
    def __init__(self):
        self.dlcs = {}
        self.performance_stats = {}
        self.thread_pool = MagicMock()
        self.process_pool = MagicMock()
    
    def log_info(self, msg):
        pass
        
    def log_warning(self, msg):
        pass
        
    def log_error(self, msg):
        pass

    def get_dlc(self, name):
        return self.dlcs.get(name)


@pytest.fixture
def mock_brain():
    return MockBrainCore()


def test_distributed_dlc(mock_brain):
    """分布式计算DLC不依赖numpy，可以直接测试。"""
    dist_dlc = DistributedComputingDLC(mock_brain)
    mock_brain.dlcs["Distributed Computing"] = dist_dlc
    dist_dlc.initialize()
    
    assert dist_dlc.manifest.name == "Distributed Computing"


def test_hardware_dlc(mock_brain):
    """硬件加速DLC测试（需要numpy）。"""
    pytest.importorskip("numpy", reason="numpy not installed")
    
    from dlcs.brain_dlc_hardware import HardwareAcceleratorDLC
    dlc = HardwareAcceleratorDLC(mock_brain)
    assert dlc.manifest.name == "Hardware Accelerator"
    dlc.initialize()
    mock_brain.dlcs[dlc.manifest.name] = dlc
    
    # Test basics
    cpu = dlc.get_device("cpu")
    assert cpu.__class__.__name__ == "CPUDevice"


def test_nn_dlc(mock_brain):
    """神经网络算子DLC测试（需要numpy）。"""
    pytest.importorskip("numpy", reason="numpy not installed")
    
    from dlcs.brain_dlc_hardware import HardwareAcceleratorDLC
    from dlcs.brain_dlc_nn import NeuralNetworkOperatorsDLC
    
    # NN depends on Hardware
    hw_dlc = HardwareAcceleratorDLC(mock_brain)
    mock_brain.dlcs["Hardware Accelerator"] = hw_dlc
    hw_dlc.initialize()
    
    nn_dlc = NeuralNetworkOperatorsDLC(mock_brain)
    mock_brain.dlcs["Neural Network Operators"] = nn_dlc
    nn_dlc.initialize()
    
    assert nn_dlc.manifest.name == "Neural Network Operators"
    # Basic tensor test
    units = nn_dlc.provide_computational_units()
    TensorNode = units["Tensor"]
    t = TensorNode([1.0, 2.0, 3.0])
    assert t.data[0] == 1.0


def test_workflow_dlc(mock_brain):
    """工作流DLC测试（需要numpy）。"""
    pytest.importorskip("numpy", reason="numpy not installed")
    
    from dlcs.brain_dlc_hardware import HardwareAcceleratorDLC
    from dlcs.brain_dlc_nn import NeuralNetworkOperatorsDLC
    from dlcs.brain_dlc_workflow import NeuralWorkflowDLC
    
    # Workflow depends on NN
    hw_dlc = HardwareAcceleratorDLC(mock_brain)
    mock_brain.dlcs["Hardware Accelerator"] = hw_dlc
    hw_dlc.initialize()
    
    nn_dlc = NeuralNetworkOperatorsDLC(mock_brain)
    mock_brain.dlcs["Neural Network Operators"] = nn_dlc
    nn_dlc.initialize()
    
    wf_dlc = NeuralWorkflowDLC(mock_brain)
    mock_brain.dlcs["Neural Workflow Engine"] = wf_dlc
    wf_dlc.initialize()
    
    assert wf_dlc.manifest.name == "Neural Workflow Manager"
