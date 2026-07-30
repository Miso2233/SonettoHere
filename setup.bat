@echo off
cd /d "%~dp0"

echo ========================================
echo   SonettoHere Setup
echo ========================================
echo.

if not exist "main.py" (
    echo [ERR] Please run this script from the project root.
    pause
    exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
    echo [ERR] Python not found. Please install Python 3.10+ first.
    echo       Download: https://www.python.org/downloads/
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
echo Setup complete! You can now run start.bat.
echo.
pause
