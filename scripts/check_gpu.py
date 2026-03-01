import torch
import sys
import os

print(f"Python Executable: {sys.executable}")
print(f"PyTorch Version: {torch.__version__}")
try:
    print(f"CUDA Available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA Version: {torch.version.cuda}")
        print(f"Device Count: {torch.cuda.device_count()}")
        print(f"Current Device: {torch.cuda.current_device()}")
        print(f"Device Name: {torch.cuda.get_device_name(0)}")
    else:
        print("Reason: torch.cuda.is_available() returned False.") 
        # Check if it's a CPU-only build
        if "+cpu" in torch.__version__:
            print("  -> You installed the CPU-only version of PyTorch.")
        else:
            print("  -> CUDA drivers might be missing or incompatible.")
            
except Exception as e:
    print(f"Error checking CUDA: {e}")
