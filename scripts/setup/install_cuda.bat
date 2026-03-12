@echo off
title MCA GPU Setup Utility
echo 启动 Python 环境配置脚本...
echo.

:: Auto-detect python
set "PY_CMD=python"
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    if exist "C:\Python313\python.exe" set "PY_CMD=C:\Python313\python.exe"
    if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
)

"%PY_CMD%" tools\gpu_setup.py

echo.
echo ==========================================================
echo Script finished.
pause
