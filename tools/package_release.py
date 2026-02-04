import shutil
import os
import zipfile
from pathlib import Path

def zip_dir(source_dir, output_filename, exclude_dirs=None):
    """
    压缩目录，支持排除指定文件夹名
    """
    if exclude_dirs is None:
        exclude_dirs = []
    
    source_path = Path(source_dir)
    parent_dir = source_path.parent
    
    print(f"[Compressing] {output_filename} ...")
    
    with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_path):
            # 修改 dirs 列表以原地排除目录 (os.walk 特性)
            # 注意：这会阻止 os.walk 进入这些目录
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                file_path = Path(root) / file
                # 计算相对路径，使得压缩包内以 MCA_Brain_System_v1.0 开头
                arcname = file_path.relative_to(parent_dir)
                zipf.write(file_path, arcname)
    
    print(f"[Created] {output_filename}")

def main():
    # 基础路径配置
    project_root = Path(__file__).resolve().parent.parent
    dist_dir = project_root / "dist" / "MCA_Brain_System_v1.0"
    release_dir = project_root / "releases"
    
    if not dist_dir.exists():
        print(f"[Error] Build directory not found: {dist_dir}")
        print("Please run pack.bat first.")
        return

    # 创建输出目录
    release_dir.mkdir(exist_ok=True)
    
    # 1. 打包 Lite 版 (排除 lib 目录)
    lite_zip = release_dir / "MCA_Brain_System_v1.0.0_LITE.zip"
    zip_dir(dist_dir, lite_zip, exclude_dirs=['lib'])
    
    # 2. 打包 Full 版 (包含所有)
    full_zip = release_dir / "MCA_Brain_System_v1.0.0_FULL.zip"
    zip_dir(dist_dir, full_zip, exclude_dirs=[])
    
    print("\n" + "="*50)
    print("Release Packaging Complete!")
    print(f"LITE Version: {lite_zip}")
    print(f"FULL Version: {full_zip}")
    print("="*50)

if __name__ == "__main__":
    main()
