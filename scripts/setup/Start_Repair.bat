@echo off
echo ========================================================
echo       MCA 环境自动修复工具 (Python Wrapper)
echo ========================================================
echo.
echo 这个脚本只是个 Python 包装器，因为 Batch 脚本处理复杂逻辑太容易崩了。
echo.

:: 1. Find Python
set "PY_EXE="
if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python313\python.exe" (
    set "PY_EXE=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python313\python.exe"
) else (
    where python >nul 2>&1
    if not errorlevel 1 set "PY_EXE=python"
)

if "%PY_EXE%"=="" (
   echo [ERROR] 没找到 Python。
   echo 请输入 python.exe 的完整路径:
   set /p PY_EXE=
)

echo 使用 Python: "%PY_EXE%"
echo.

:: 2. Run Repair Script
"%PY_EXE%" "%~dp0repair_mca_env.py"

echo.
echo Wrapper script finished.
pause
