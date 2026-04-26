@echo off
title MCA GPU Setup Utility
echo 启动 GPU/CUDA 环境配置向导...
echo.

if exist "%~dp0install_env.bat" (
    call "%~dp0install_env.bat"
) else (
    echo [ERROR] 未找到 install_env.bat，请检查 scripts\setup 目录完整性。
)

echo.
echo ==========================================================
echo Script finished.
pause
