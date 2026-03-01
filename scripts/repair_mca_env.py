import sys
import subprocess
import os
import platform
import re

def log(msg):
    print(f"[MCA Repair] {msg}")

def run_cmd(cmd):
    log(f"Running: {cmd}")
    try:
        subprocess.check_call(cmd, shell=True)
    except subprocess.CalledProcessError as e:
        log(f"Error executing command: {e}")
        return False
    return True

def get_cuda_version():
    try:
        # Try to use nvidia-smi
        smi = subprocess.check_output(["nvidia-smi"], encoding="utf-8", stderr=subprocess.STDOUT)
        match = re.search(r"CUDA Version: (\d+\.\d+)", smi)
        if match:
            return float(match.group(1))
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    return 0.0

def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("="*60)
    print("      MCA AI Environment Repair Tool (Python Logic)")
    print("="*60)
    
    py_ver = sys.version_info
    log(f"Detected Python executable: {sys.executable}")
    log(f"Detected Python Version: {py_ver.major}.{py_ver.minor}.{py_ver.micro}")
    
    cuda_ver = get_cuda_version()
    log(f"Detected System CUDA Version: {cuda_ver}")
    
    # 1. Pip Fix
    log("Step 1/3: Repairing pip environment...")
    run_cmd(f'"{sys.executable}" -m ensurepip --default-pip')
    run_cmd(f'"{sys.executable}" -m pip install --upgrade pip')

    # 2. Uninstall Clean
    log("Step 2/3: Cleaning up broken installations...")
    run_cmd(f'"{sys.executable}" -m pip uninstall -y torch torchvision torchaudio')

    # 3. Install Logic
    log("Step 3/3: Installing correct PyTorch version...")
    install_args = []
    
    # Python 3.13 requires Nightly
    if py_ver.major == 3 and py_ver.minor >= 13:
        log("Condition: Python 3.13 detected -> Using PyTorch Nightly")
        if cuda_ver >= 12.0:
             log("Condition: CUDA 12+ detected -> GPU Mode")
             # Nightly cu124
             # Note: torchaudio might fail on 3.13, and torchvision often has version mismatches in Nightly
             # Since MCA mainly uses CodeBERT (NLP), we verify torchvision is not strictly needed.
             install_args = ["--pre", "torch", "--index-url", "https://download.pytorch.org/whl/nightly/cu124"]
        else:
             log("Condition: No CUDA or old CUDA -> CPU Mode")
             install_args = ["--pre", "torch", "--index-url", "https://download.pytorch.org/whl/nightly/cpu"]
             
    # Python < 3.13 can use Stable
    else:
        if cuda_ver >= 12.1:
            log("Condition: CUDA 12.1+ detected -> Using PyTorch Stable (cu121)")
            install_args = ["torch", "--index-url", "https://download.pytorch.org/whl/cu121"]
        elif cuda_ver >= 11.8:
            log("Condition: CUDA 11.8 detected -> Using PyTorch Stable (cu118)")
            install_args = ["torch", "--index-url", "https://download.pytorch.org/whl/cu118"]
        else:
            log("Condition: Fallback -> Using PyTorch CPU")
            install_args = ["torch"]

    # Execute Install
    full_cmd = [sys.executable, "-m", "pip", "install"] + install_args
    cmd_str = " ".join(full_cmd)
    
    success = run_cmd(cmd_str)
    
    if success:
        print("\n" + "="*60)
        log("Verification Phase:")
        try:
            import torch
            print(f"  > Torch Version: {torch.__version__}")
            print(f"  > CUDA Available: {torch.cuda.is_available()}")
            if torch.cuda.is_available():
                print(f"  > Device: {torch.cuda.get_device_name(0)}")
                print("\n[SUCCESS] Your environment is fixed and GPU is ready!")
            else:
                print("\n[INFO] Installed successfully, but running on CPU.")
        except ImportError as e:
            print(f"\n[ERROR] Installation seemed successful but import failed: {e}")
    else:
        print("\n[BFATAL] Pip failed to install packages.")

    print("="*60)
    input("Press Enter to exit...")

if __name__ == "__main__":
    main()
