"""Brain System DLCs re-export.

This package provides compatibility imports under brain_system.dlcs.*
while actual implementations live in the top-level dlcs package.
"""

from dlcs.brain_dlc_distributed import DistributedComputingDLC
from dlcs.brain_dlc_hardware import HardwareAcceleratorDLC
from dlcs.brain_dlc_nn import NeuralNetworkOperatorsDLC
from dlcs.brain_dlc_workflow import NeuralWorkflowDLC

__all__ = [
    "DistributedComputingDLC",
    "HardwareAcceleratorDLC",
    "NeuralNetworkOperatorsDLC",
    "NeuralWorkflowDLC",
]
