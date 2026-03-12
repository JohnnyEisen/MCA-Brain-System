@echo off
setlocal EnableDelayedExpansion

echo [INFO] Detect Python Environment...

:: 1. 尝试寻找 Python 3.13 (项目开发环境)
py -0 >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] Python Launcher found. Checking for 3.13...
    py -3.13 --version >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=py -3.13"
        echo [INFO] Using Python 3.13 via launcher.
        goto :FOUND_PYTHON
    )
)

:: 2. 尝试检查当前 PATH 的 python 是否符合要求
python --version 2>&1 | findstr "3.13" >nul
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python"
    echo [INFO] Using 'python' from PATH (Version 3.13).
    goto :FOUND_PYTHON
)

:: 3. 如果都没找到，可能用户配置了具体的绝对路径，或者没有安装 3.13
:: 尝试在默认位置寻找 (Generic Path)
set "LOCAL_Py313=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if exist "%LOCAL_Py313%" (
    set "PYTHON_CMD="%LOCAL_Py313%""
    echo [INFO] Using Auto-detected Path: %LOCAL_Py313%
    goto :FOUND_PYTHON
)

echo [WARN] Could not find Python 3.13 automatically.
echo [WARN] Will use default 'python' command (May be the wrong version: %PYTHON_VERSION%).
set "PYTHON_CMD=python"

:FOUND_PYTHON
%PYTHON_CMD% --version
echo [INFO] Starting build process v1.0.0...

:: Ensure PyInstaller is installed in the TARGET environment
%PYTHON_CMD% -m pip show pyinstaller >nul 2>&1
if %errorlevel% equ 0 goto :SKIP_INSTALL

echo [WARN] Environment appears incomplete. Installing dependencies...
echo [1/2] Installing Build Tools [PyInstaller]...
%PYTHON_CMD% -m pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple
if %errorlevel% neq 0 (
        echo [ERROR] Failed to install PyInstaller. Check network.
        pause
        exit /b 1
)

echo [2/2] Installing Project Dependencies [Safe to skip if already installed]...
%PYTHON_CMD% -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

:SKIP_INSTALL
:: Clean previous builds

:: Clean previous builds
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del *.spec

:: Prepare Build Assets (Clean Data)
echo [INFO] Preparing Clean Build Assets...
%PYTHON_CMD% "scripts/build/prepare_build.py"
if %errorlevel% neq 0 (
    echo [ERROR] Failed to prepare assets.
    pause
    exit /b 1
)

:: Build command
:: Logic moved to scripts/build/run_build.py for stability and readability
echo [INFO] Running PyInstaller (via scripts/build/run_build.py)...
%PYTHON_CMD% "scripts/build/run_build.py"

if %errorlevel% equ 0 goto :BUILD_SUCCESS
echo [ERROR] Build failed. Check the output above.
pause
exit /b 1

:BUILD_SUCCESS
echo [SUCCESS] Core Build complete! App is in dist/MCA_Brain_System_v1.2.0/
echo [INFO] Collecting external libraries (lib folder)...
%PYTHON_CMD% "scripts/build/collect_libs.py"

echo [INFO] Creating release archives (lite / full)...
%PYTHON_CMD% "scripts/build/package_release.py"

echo [INFO] Cleaning up temp assets...
if exist build_assets rmdir /s /q build_assets

pause
