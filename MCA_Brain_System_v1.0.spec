# -*- mode: python ; coding: utf-8 -*-

# MCA Brain System - Secure EXE Packaging Config
# PyInstaller options for security and size optimization

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('build_assets/analysis_data', 'analysis_data'), 
        ('build_assets/config', 'config'), 
        ('build_assets/plugins', 'plugins')
    ],
    hiddenimports=[
        'brain_system', 
        'dlcs', 
        'mca_core.detectors',
        # Security: hide imports
        'mca_core.security',
        'mca_core.launcher',
    ],
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'networkx', 'PIL', 'numpy', 
        'scipy', 'psutil', 'packaging',
        'test', 'tests',  # Exclude test files
        'debug',  # Exclude debug modules
    ],
    noarchive=False,
    # Security: optimize bytecode
    optimize=2,  # Maximum optimization
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MCA_Brain_System_v1.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,  # Strip debug symbols
    upx=True,
    upx_exclude=['vcruntime140.dll'],  # Exclude antivirus-false-positive files
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app_icon.ico'],
    # Resource protection
    resources=[
        ('config', 'config', 'DATA'),  # Read-only config
    ],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=['vcruntime140.dll'],
    name='MCA_Brain_System_v1.0',
)
