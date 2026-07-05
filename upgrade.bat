@echo off
cd /d "%~dp0"

echo ========================================
echo   SonettoHere - Config Upgrade
echo ========================================
echo.

if not exist "main.py" (
    echo [ERR] Run this script from the project root.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [ERR] Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)

echo [1/2] Pulling updates and running migrations ...
.venv\Scripts\python upgrade.py
set EXIT_CODE=%ERRORLEVEL%

echo.
echo ========================================
if %EXIT_CODE% neq 0 (
    echo  Result: [FAILED] Check the log above.
) else (
    echo  Result: [OK]
)
echo ========================================

echo.
echo Press any key to close ...
pause >nul
