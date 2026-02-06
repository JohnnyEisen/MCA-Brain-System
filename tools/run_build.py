import sys
import subprocess
from pathlib import Path

def check_pyinstaller():
    try:
        import PyInstaller
        return True
    except ImportError:
        return False

def install_pyinstaller():
    print("[Build] Installing PyInstaller")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller", "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"])

def run_build():
    if not check_pyinstaller():
        install_pyinstaller()
    
    import PyInstaller.__main__
    
    print("[Build] Starting PyInstaller build")
    
    # 构建参数列表
    # 注意：Windows 下分隔符是 ;，Linux/Mac 是 :
    sep = ";" if sys.platform.startswith("win") else ":"
    
    args = [
        '--noconfirm',
        '--onedir',
        '--windowed',
        '--name=MCA_Brain_System_v1.0',
        '--icon=app_icon.ico',
        
        # 数据文件映射
        f'--add-data=build_assets/analysis_data{sep}analysis_data',
        f'--add-data=build_assets/config{sep}config',
        f'--add-data=build_assets/plugins{sep}plugins',
        
        # 钩子与隐藏导入
        '--additional-hooks-dir=hooks',
        '--hidden-import=brain_system',
        '--hidden-import=dlcs',
        '--hidden-import=mca_core.detectors',
        
        # 排除外部库（由 collect_libs.py 复制到 lib 文件夹）
        '--exclude-module=matplotlib',
        '--exclude-module=networkx',
        '--exclude-module=PIL',
        '--exclude-module=numpy',
        '--exclude-module=scipy',
        '--exclude-module=psutil',
        '--exclude-module=packaging',
        
        '--clean',
        'main.py'
    ]
    
    # 执行打包
    PyInstaller.__main__.run(args)

if __name__ == "__main__":
    try:
        run_build()
    except Exception as e:
        print(f"[Error] Build failed: {e}")
        sys.exit(1)
