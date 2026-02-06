import os
import shutil
import site
import sys
from pathlib import Path

# 定义需要作为外部依赖分离的库
# 这些库将被从 EXE 中排除，并复制到 lib 文件夹中
EXTENSIONS = [
    "matplotlib",
    "mpl_toolkits",
    "networkx",
    "numpy",  # 核心依赖，如果分离可能需要当心 DLL 问题，但为了轻量化可以尝试
    "PIL",    # Pillow
    "scipy",
    "psutil",
    "packaging"
]

def get_package_path(package_name):
    """尝试在当前的 site-packages 中找到包路径"""
    for site_pkg in site.getsitepackages():
        # 常见结构: site-packages/numpy
        p = Path(site_pkg) / package_name
        if p.exists() and p.is_dir():
            return p
        # 或者是 .py 文件 (单文件模块)
        p_py = Path(site_pkg) / f"{package_name}.py"
        if p_py.exists():
            return p_py
    return None

def main():
    print("[Info] Collecting external libraries...")
    
    # 输出目录：dist/lib
    base_dir = Path(__file__).resolve().parent.parent
    dist_lib = base_dir / "dist" / "MCA_Brain_System_v1.0" / "lib"
    
    if dist_lib.exists():
        print(f"[Info] Removing old directory: {dist_lib}")
        shutil.rmtree(dist_lib)
    dist_lib.mkdir(parents=True, exist_ok=True)
    
    print(f"[Info] Target directory: {dist_lib}")
    
    success_count = 0
    for pkg in EXTENSIONS:
        src = get_package_path(pkg)
        if not src:
            print(f"[Warn] Library not found: {pkg}. Skipped.")
            continue
            
        print(f"[Info] Copying {pkg}...")
        try:
            if src.is_dir():
                shutil.copytree(src, dist_lib / pkg)
            else:
                shutil.copy2(src, dist_lib)
            success_count += 1
        except Exception as e:
            print(f"[Error] Failed to copy {pkg}: {e}")

    print("-" * 40)
    print(f"External library collection complete. Total: {success_count}")
    print("Options:")
    print(f"1. Lite: remove '{dist_lib}' and ship only the EXE")
    print(f"2. Full: keep '{dist_lib}' with the EXE")

if __name__ == "__main__":
    main()
