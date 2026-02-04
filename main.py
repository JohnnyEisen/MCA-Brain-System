import sys
import os

# --- HOTFIX SYSTEM (热修补丁系统) ---
# 允许加载 executable 同级目录下的 'patches' 文件夹中的源码。
# 这使得可以在不重新编译/打包 EXE 的情况下，通过分发 .py 文件来更新核心逻辑。
# 将 'patches' 目录优先级提至最高 (index 0)。
if getattr(sys, 'frozen', False):
    # 打包运行环境
    application_path = os.path.dirname(sys.executable)
    
    # 1. Hotfix (最高优先级)
    patch_dir = os.path.join(application_path, "patches")
    if os.path.exists(patch_dir):
        sys.path.insert(0, patch_dir)
        print(f"[Hotfix] Loaded patches from: {patch_dir}")
        
    # 2. External Libs (用于加载被排除的瘦身组件，如 numpy, PIL)
    # 必须加入 sys.path，否则 import 会失败导致闪退
    lib_dir = os.path.join(application_path, "lib")
    if os.path.exists(lib_dir):
        sys.path.append(lib_dir)
else:
    # 开发环境 (可选：也可以支持 patches 目录调试)
    pass
# ------------------------------------

def main():
    try:
        # 尝试从 mca_core.launcher 启动
        # 这允许通过 patches/mca_core/launcher.py 修复启动逻辑
        from mca_core.launcher import launch_app
        launch_app()
    except ImportError:
        # 兼容旧版本结构（如果 launcher 不存在）
        # 这里是最后的兜底，防止重构导致完全无法启动
        import tkinter as tk
        from mca_core.app import MinecraftCrashAnalyzer
        root = tk.Tk()
        app = MinecraftCrashAnalyzer(root)
        root.mainloop()

if __name__ == "__main__":
    main()
