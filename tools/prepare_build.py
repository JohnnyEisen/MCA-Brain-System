import os
import shutil
import sys
from pathlib import Path

def prepare_assets():
    """
    准备构建所需的静态资源，过滤掉开发环境的杂质（日志、测试数据、源码等）。
    """
    root_dir = Path(__file__).resolve().parent.parent
    dist_assets_dir = root_dir / "build_assets"
    
    if dist_assets_dir.exists():
        shutil.rmtree(dist_assets_dir)
    dist_assets_dir.mkdir()
    
    print(f"[Prepare] 构建资产目录: {dist_assets_dir}")

    # 1. 处理 analysis_data (仅保留 JSON 数据库)
    src_data = root_dir / "analysis_data"
    dst_data = dist_assets_dir / "analysis_data"
    dst_data.mkdir()
    
    allow_extensions = ['.json']
    # 也可以显式白名单
    allow_files = [
        "diagnostic_rules.json",
        "gpu_issues.json",
        "loader_database.json",
        "mod_conflicts.json",
        "mod_database.json"
    ]
    
    print(f"[Prepare] 处理 Analysis Data...")
    for f in os.listdir(src_data):
        src_f = src_data / f
        if src_f.is_file() and (f in allow_files or f.endswith('.json')):
            shutil.copy2(src_f, dst_data)
            print(f"  + {f}")
        else:
            print(f"  - 忽略: {f}")

    # 2. 处理 Config (仅保留 JSON 及其结构)
    src_conf = root_dir / "config"
    dst_conf = dist_assets_dir / "config"
    dst_conf.mkdir()
    
    print(f"[Prepare] 处理 Config...")
    if (src_conf / "brain_config.json").exists():
        shutil.copy2(src_conf / "brain_config.json", dst_conf)
        print(f"  + brain_config.json")
    
    # 3. 处理 Plugins (保留 readme 和结构)
    src_plugin = root_dir / "plugins"
    dst_plugin = dist_assets_dir / "plugins"
    dst_plugin.mkdir()
    # 复制说明文件
    for f in os.listdir(src_plugin):
        if f.startswith("README"):
             shutil.copy2(src_plugin / f, dst_plugin)

    print("[Prepare] 资产准备完成。")

if __name__ == "__main__":
    prepare_assets()
