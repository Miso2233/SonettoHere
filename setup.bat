@echo off
cd /d "%~dp0"

echo ========================================
echo   SonettoHere Setup
echo ========================================
echo.

if not exist "main.py" (
    echo [ERR] 请确保在项目根目录运行此脚本。
    pause
    exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
    echo [ERR] 未找到 Python，请先安装 Python 3.10+。
    echo       下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)

python setup.py
if errorlevel 1 (
    echo.
    pause
    exit /b 1
)

echo.
echo 初始化完成！现在可以双击 start.bat 启动了。
echo.
pause
