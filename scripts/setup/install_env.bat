@echo off
chcp 65001 >nul
echo ===================================================
echo     Minecraft Crash Analyzer - 环境安装脚本
echo ===================================================
echo.

REM 自动定位 Python 3.13
set "PYTHON_EXE=python"
if exist "C:\Users\20122\AppData\Local\Programs\Python\Python313\python.exe" (
    set "PYTHON_EXE=C:\Users\20122\AppData\Local\Programs\Python\Python313\python.exe"
    echo [Target] 检测到 Python 3.13: %PYTHON_EXE%
) else (
    echo [Target] 使用默认 'python' 命令
)

echo.
echo [1/3] 检测 Python 环境...
"%PYTHON_EXE%" --version
if errorlevel 1 (
    echo 找不到 Python! 请安装 Python 3.9+ 并添加到 PATH 环境变量。
    pause
    exit /b
)

echo.
echo [网络配置]
set /p USE_MIRROR="是否在中国大陆/网络较差地区? (Y/N) [Default: Y]: "
if /i "%USE_MIRROR%"=="Y" (
    echo.
    echo [Deepin/China Optimization Mode]
    echo 1. Setting Pip source to Tsinghua University mirror...
    set PIP_ARGS=-i https://pypi.tuna.tsinghua.edu.cn/simple
    
    echo 2. Setting HuggingFace mirror environment variable...
    REM Set for current session
    set HF_ENDPOINT=https://hf-mirror.com
    REM Set permanently for future app runs
    setx HF_ENDPOINT "https://hf-mirror.com" >nul
    echo    - HF_ENDPOINT set to https://hf-mirror.com
) else (
    set PIP_ARGS=
)

echo.
echo [Step 2] Installing PyTorch...
set /p INSTALL_GPU="Do you want to install NVIDIA GPU support (CUDA 12.1)? (Y/N) [Default N]: "
if /i "%INSTALL_GPU%"=="Y" (
    echo [GPU Mode] Installing PyTorch with CUDA 12.1 support...
    echo Note: This uses the official PyTorch repository to ensure compatibility.
    "%PYTHON_EXE%" -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
) else (
    echo [CPU Mode] Installing standard PyTorch...
    "%PYTHON_EXE%" -m pip install torch torchvision torchaudio %PIP_ARGS%
)

echo.
echo [Step 3] Installing Transformers (for CodeBERT)...
"%PYTHON_EXE%" -m pip install transformers %PIP_ARGS%

echo.
echo [Step 4] Installing Scikit-Learn (optional utils)...
"%PYTHON_EXE%" -m pip install scikit-learn %PIP_ARGS%

echo.
echo ===================================================
echo Installation complete! 
echo.
if /i "%USE_MIRROR%"=="Y" (
    echo NOTE: Please RESTART your terminal/VS Code to ensure 
    echo the HF_ENDPOINT environment variable takes effect.
)
echo ===================================================
pause
