try:
    import importlib
    _hooks = importlib.import_module("PyInstaller.utils.hooks")
    collect_submodules = _hooks.collect_submodules
except Exception:
    # 防止 IDE 报错 (Pylance)，实际打包时 PyInstaller 环境会有此包
    def collect_submodules(p):
        return []

# 收集 mca_core.detectors 下的所有子模块，防止打包时丢失
hiddenimports = collect_submodules('mca_core.detectors')
