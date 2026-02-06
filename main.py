import sys
import os

# Patch loader
# Loads optional overrides from a sibling 'patches' folder when running as a frozen executable.
# This enables patch delivery without rebuilding the EXE.
if getattr(sys, 'frozen', False):
    # Frozen runtime
    application_path = os.path.dirname(sys.executable)
    
    # Patches (highest priority)
    patch_dir = os.path.join(application_path, "patches")
    if os.path.exists(patch_dir):
        sys.path.insert(0, patch_dir)
        print(f"[Hotfix] Loaded patches from: {patch_dir}")
        
    # External libs (used when heavy dependencies are shipped in lib/)
    # Must be added to sys.path to avoid import failures
    lib_dir = os.path.join(application_path, "lib")
    if os.path.exists(lib_dir):
        sys.path.append(lib_dir)
else:
    # Development environment (optional)
    pass
# End patch loader

def main():
    try:
        # Primary entry point
        from mca_core.launcher import launch_app
        launch_app()
    except ImportError:
        # Fallback for legacy layout
        import tkinter as tk
        from mca_core.app import MinecraftCrashAnalyzer
        root = tk.Tk()
        app = MinecraftCrashAnalyzer(root)
        root.mainloop()

if __name__ == "__main__":
    main()
