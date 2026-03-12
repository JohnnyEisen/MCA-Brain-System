import sys
print(f"Python: {sys.executable}")
try:
    import torch
    print(f"Torch version: {torch.__version__}")
    print(f"Torch cuda available: {torch.cuda.is_available()}")
except ImportError as e:
    print(f"Failed to import torch: {e}")
except Exception as e:
    print(f"Error importing torch: {e}")

try:
    import transformers
    print(f"Transformers version: {transformers.__version__}")
except ImportError as e:
    print(f"Failed to import transformers: {e}")
except Exception as e:
    print(f"Error importing transformers: {e}")

import brain_system.utils
print(f"Utils location: {brain_system.utils.__file__}")
