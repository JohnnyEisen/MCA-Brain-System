import tkinter as tk
from tkinter import messagebox
import sys
import importlib.util
import os
import site

from mca_core.app import MinecraftCrashAnalyzer

def launch_app():
    """
    真正的应用程序入口点。
    这个函数可以通过 patches/mca_core/launcher.py 进行热替换/修复。
    """
    
    # --- 0. 外部依赖挂载 (External Lib Loader) ---
    # 允许用户在 exe 同级目录下创建 'lib' 文件夹，存放额外的 Python 库
    # 这对于解决 DLC 引入的新依赖缺失问题至关重要
    IS_FROZEN = getattr(sys, 'frozen', False)
    if IS_FROZEN:
        base_dir = os.path.dirname(sys.executable)
        external_lib_dir = os.path.join(base_dir, "lib")
        
        if os.path.exists(external_lib_dir):
            try:
                # 将其加入 sys.path，site.addsitedir 会自动处理 .pth 文件
                site.addsitedir(external_lib_dir)
                # 显式前置插入，确保优先级高于内置的（如果需要覆盖的话，通常不用）
                if external_lib_dir not in sys.path:
                    sys.path.insert(0, external_lib_dir)
                print(f"[Launcher] Loaded external libraries from: {external_lib_dir}")
            except Exception as e:
                print(f"[Launcher] Failed to load external libs: {e}")

    # --- 环境健康检查 ---
    missing_deps = []
    required = {
        "networkx": "用于绘制 Mod 依赖图",
        "matplotlib": "用于绘制崩溃原因饼图",
        "psutil": "用于系统资源监控"
    }
    
    # 注意：在打包环境中，有些库可能已经被 PyInstaller 处理过，find_spec 可能会有不同行为
    # 但基本的 import是没问题的。
    for pkg, desc in required.items():
        try:
            importlib.import_module(pkg)
        except ImportError:
            # 尝试查找 spec (开发环境)
            if importlib.util.find_spec(pkg) is None:
                missing_deps.append(f"{pkg} ({desc})")

    root = tk.Tk()

    if missing_deps:
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        # 针对打包环境显示更有用的提示
        if IS_FROZEN:
             warning_msg = (
                f"检测到核心功能依赖缺失！\n\n"
                f"部分功能（如绘图、监控）将不可用。这可能是因为您启用了包含新依赖的 DLC，但打包环境中未包含这些库。\n\n"
                f"缺失列表:\n" + 
                "\n".join(f"• {item}" for item in missing_deps) + "\n\n"
                f"解决方案:\n"
                f"1. 在程序目录（MCA_Brain_System.exe 所在位置）新建一个名为 'lib' 的文件夹。\n"
                f"2. 将缺失库的 Python 包（文件夹）复制到该 'lib' 目录中。\n"
                f"3. 重启程序，系统会自动加载 'lib' 中的扩展库。"
             )
             messagebox.showwarning("依赖缺失 (运行环境)", warning_msg)
        else:
            py_path = sys.executable
            warning_msg = (
                f"检测到运行环境可能导致功能受限！\n\n"
                f"当前 Python 版本: {py_ver}\n"
                f"解释器路径: {py_path}\n\n"
                f"缺失以下可选依赖库:\n" + 
                "\n".join(f"• {item}" for item in missing_deps) + "\n\n"
                f"解决方案:\n"
                f"1. 如果您安装了多个 Python，请确保使用的是正确的版本。\n"
                f"2. 或者在终端运行安装命令:\n"
                f"   pip install networkx matplotlib"
            )
            messagebox.showwarning("环境监测警告", warning_msg)

    # 实例化核心应用
    app = MinecraftCrashAnalyzer(root)
    
    # 进入主循环
    root.mainloop()
