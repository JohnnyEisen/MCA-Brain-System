# Setup Scripts Guide

## Recommended Entry Points

- `install_env.bat`
  - Main Windows setup script.
  - Installs/repairs core AI environment with optional CUDA 12.1 PyTorch path.

- `install_cuda.bat`
  - Wrapper entry for users looking for GPU setup directly.
  - Internally calls `install_env.bat`.

- `Start_Repair.bat`
  - Wrapper for `../repair_mca_env.py`.
  - Used when environment is partially broken and needs repair/reinstall logic.

## Supporting Scripts

- `collect_libs.py`
  - Packaging helper for collecting external libraries into distribution folders.

- `setup.py`
  - Legacy packaging helper kept for compatibility.

## Notes

- Prefer `install_env.bat` for first-time setup.
- Use `python scripts/check_gpu.py` after installation to verify CUDA availability.
