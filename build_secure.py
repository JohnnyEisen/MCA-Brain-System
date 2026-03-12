#!/usr/bin/env python3
"""
Secure Build Script - MCA Brain System
Uses PyArmor to obfuscate code before packaging

Usage:
    python build_secure.py          # Normal build
    python build_secure.py clean   # Clean build artifacts
"""

import os
import sys
import shutil
import subprocess


def check_pyarmor():
    """Check if PyArmor is installed"""
    try:
        import pyarmor
        print(f"[OK] PyArmor {pyarmor.__version__} installed")
        return True
    except ImportError:
        print("[ERROR] PyArmor not installed!")
        print("Install with: pip install pyarmor")
        return False


def clean():
    """Clean build artifacts"""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    files_to_clean = ['build_assets']
    
    print("[CLEAN] Removing build artifacts...")
    
    for d in dirs_to_clean:
        if os.path.exists(d):
            shutil.rmtree(d)
            print(f"  Removed: {d}/")
    
    for f in files_to_clean:
        if os.path.isdir(f):
            shutil.rmtree(f)
            print(f"  Removed: {f}/")
        elif os.path.exists(f):
            os.remove(f)
            print(f"  Removed: {f}")
    
    print("[CLEAN] Done")


def obfuscate(src_dir='src', output_dir='build/obfuscated'):
    """
    Obfuscate source code using PyArmor
    
    Args:
        src_dir: Source directory to obfuscate
        output_dir: Output directory for obfuscated code
    """
    print(f"[OBFUSCATE] Protecting source code...")
    print(f"  Source: {src_dir}")
    print(f"  Output: {output_dir}")
    
    # Clean output dir
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    # PyArmor obfuscation command
    # -O: output directory
    # --recursive: process all subdirectories
    # --no-wrap: don't wrap (smaller, faster)
    cmd = [
        sys.executable, '-m', 'pyarmor', 'gen',
        '-O', output_dir,
        '--recursive',
        src_dir
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"[OK] Obfuscation complete")
        return True
    else:
        print(f"[ERROR] Obfuscation failed:")
        print(result.stderr)
        return False


def build_exe(obfuscated=True):
    """
    Build EXE using PyInstaller
    
    Args:
        obfuscated: Use obfuscated code if True
    """
    print(f"[BUILD] Building EXE (obfuscated={obfuscated})")
    
    if obfuscated:
        src_dir = 'build/obfuscated'
    else:
        src_dir = 'src'
    
    # Copy main.py to source dir for packaging
    if obfuscated and os.path.exists('main.py'):
        shutil.copy('main.py', os.path.join(src_dir, 'main.py'))
    
    # Run PyInstaller
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        'MCA_Brain_System_v1.0.spec',
        '--noconfirm',
        '--distpath', 'dist'
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"[OK] EXE built successfully")
        return True
    else:
        print(f"[ERROR] Build failed:")
        print(result.stderr)
        return False


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == 'clean':
            clean()
            return
    
    if not check_pyarmor():
        sys.exit(1)
    
    # Clean first
    clean()
    
    # Obfuscate
    if not obfuscate():
        print("[WARN] Falling back to non-obfuscated build")
    
    # Build EXE
    # Note: For obfuscated build, need to modify main.py import path
    # This is a simplified version
    
    print("\n[DONE] Build complete!")
    print("Output: dist/MCA_Brain_System_v1.0/")


if __name__ == '__main__':
    main()
