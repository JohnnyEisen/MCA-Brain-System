import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))
from dlcs.brain_dlc_codebert import CodeBertDLC
from brain_system import BrainCore

core = BrainCore()
dlc = CodeBertDLC(core)
print(dir(dlc))
