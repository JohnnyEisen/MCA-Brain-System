import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))
from mca_core.detectors.registry import DetectorRegistry
registry = DetectorRegistry()
registry.load_builtins()
print([d.get_name() for d in registry.list()])
