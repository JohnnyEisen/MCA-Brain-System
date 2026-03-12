"""Application Launcher - SECURE VERSION for EXE packaging."""

import tkinter as tk
from tkinter import messagebox
import sys
import importlib.util
import os
import site
import logging
import urllib.request

# Fix console encoding on Windows
if sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception as e:
        print(f"Warning: Failed to set console encoding: {e}")

from mca_core.app import MinecraftCrashAnalyzer

# Detect if running as frozen exe
IS_FROZEN = getattr(sys, 'frozen', False)
if IS_FROZEN:
    # Running as PyInstaller exe
    MEIPASS = getattr(sys, '_MEIPASS', '')
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def launch_app():
    """Application entry point"""
    logger = logging.getLogger(__name__)
    
    # --- 0. External dependency loading (EXE mode) ---
    if IS_FROZEN:
        external_lib_dir = os.path.join(BASE_DIR, "lib")
        
        if os.path.exists(external_lib_dir):
            try:
                # Security validation before loading
                from mca_core.security import ExternalLibValidator
                is_safe, warnings = ExternalLibValidator.validate_lib_directory(external_lib_dir)
                
                if not is_safe:
                    print(f"[Security Warning] lib directory has risks:")
                    for w in warnings:
                        print(f"  - {w}")
                    print("[Security] Proceeding with validation warnings...")
                
                # V-010 Fix: Use sys.path directly instead of site.addsitedir()
                # site.addsitedir() executes .pth files which is a security risk
                if external_lib_dir not in sys.path:
                    sys.path.insert(0, external_lib_dir)
                print(f"[Launcher] Loaded external libraries from: {external_lib_dir}")
                
            except Exception as e:
                print(f"[Launcher] Failed to load external libs: {e}")
    
    # --- 1. Security checks ---
    try:
        from mca_core.security import DebugDetector, IntegrityChecker, get_default_repair
        
        # Debugger detection
        if DebugDetector.is_debugging():
            print("[Security] Debugger environment detected")
        
        # VM detection
        if DebugDetector.is_virtual_machine():
            print("[Security] Virtual machine environment detected")
        
        # File integrity check
        checker = IntegrityChecker()
        
        # Try online repair first
        repair = get_default_repair()
        net_fix_success = False
        
        if repair:
            try:
                urllib.request.urlopen("https://api.github.com", timeout=5)
                is_valid, modified = checker.verify_integrity()
                if not is_valid:
                    print(f"[Security Warning] Files modified: {modified}")
                    print("[Security] Fetching correct versions from GitHub...")
                    proj_base = BASE_DIR
                    for file_path in modified:
                        success, msg = repair.verify_and_repair(file_path, proj_base)
                        print(f"[Security] {file_path}: {msg}")
                        if success and "repaired" in msg.lower():
                            net_fix_success = True
            except Exception as net_error:
                print(f"[Security] Network unavailable: {net_error}")
        
        # Offline mode
        if not net_fix_success:
            is_valid, modified = checker.verify_integrity()
            if not is_valid:
                print(f"[Security Warning] Files modified: {modified}")
                baseline = checker.load_baseline()
                if baseline:
                    print("[Security] Offline mode: using local baseline")
                else:
                    print("[Security] No baseline, skipping validation")
                    
    except Exception as e:
        logger.warning(f"Security check skipped: {e}")

    # --- 2. Dependency check ---
    missing_deps = []
    required = {
        "networkx": "Mod dependency graph",
        "matplotlib": "Crash cause pie chart",
        "psutil": "System resource monitoring"
    }
    
    for pkg, desc in required.items():
        try:
            importlib.import_module(pkg)
        except ImportError:
            if importlib.util.find_spec(pkg) is None:
                missing_deps.append(f"{pkg} ({desc})")

    root = tk.Tk()

    if missing_deps:
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        if IS_FROZEN:
            warning_msg = (
                f"Core dependencies missing!\n\n"
                f"Some features (graph, monitoring) will be unavailable.\n\n"
                f"Missing:\n" + 
                "\n".join(f"• {item}" for item in missing_deps) + "\n\n"
                f"Solution:\n"
                f"1. Create 'lib' folder in program directory.\n"
                f"2. Copy missing Python packages to 'lib'.\n"
                f"3. Restart the program."
            )
            messagebox.showwarning("Missing Dependencies", warning_msg)
        else:
            py_path = sys.executable
            warning_msg = (
                f"Runtime environment issue!\n\n"
                f"Python version: {py_ver}\n"
                f"Path: {py_path}\n\n"
                f"Missing:\n" + 
                "\n".join(f"• {item}" for item in missing_deps) + "\n\n"
                f"Solution:\n"
                f"pip install networkx matplotlib"
            )
            messagebox.showwarning("Environment Warning", warning_msg)

    # --- 3. Launch application ---
    app = MinecraftCrashAnalyzer(root)
    root.mainloop()


if __name__ == "__main__":
    launch_app()
