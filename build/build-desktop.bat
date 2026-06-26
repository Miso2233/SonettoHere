@echo off
chcp 65001 >nul
title SonettoHere Desktop Build

set PROJECT_ROOT=%~dp0..
set ELECTRON_DIR=%PROJECT_ROOT%\build\packaging\electron
set DIST_DIR=%PROJECT_ROOT%\dist

echo ============================================
echo  SonettoHere Desktop Build
echo ============================================
echo.

REM ── Step 1: 构建前端 ──
echo [1/4] 构建前端...
cd /d "%PROJECT_ROOT%\web"
if not exist "node_modules" (
    call npm ci
    if errorlevel 1 (
        echo [!] npm ci 失败
        pause
        exit /b 1
    )
)
call npm run build
if errorlevel 1 (
    echo [!] 前端构建失败
    pause
    exit /b 1
)
echo [OK] 前端构建完成
echo.

REM ── Step 2: PyInstaller 打包后端 ──
echo [2/4] 打包后端...
cd /d "%PROJECT_ROOT%"
call .venv\Scripts\activate
pip install pyinstaller
pyinstaller "%ELECTRON_DIR%\sonettohere.spec" --clean --noconfirm
if errorlevel 1 (
    echo [!] PyInstaller 打包失败
    pause
    exit /b 1
)
echo [OK] 后端打包完成
echo.

REM ── Step 3: 安装 Electron 依赖 ──
echo [3/4] 安装 Electron 构建依赖...
cd /d "%ELECTRON_DIR%"
if not exist "node_modules" (
    call npm ci
    if errorlevel 1 (
        echo [!] npm ci 失败
        pause
        exit /b 1
    )
)
echo [OK] Electron 依赖就绪
echo.

REM ── Step 4: 打包桌面安装包 ──
echo [4/4] 打包桌面安装包...
cd /d "%ELECTRON_DIR%"
call npx electron-builder --win --x64
if errorlevel 1 (
    echo [!] Electron 打包失败
    pause
    exit /b 1
)
echo [OK] 桌面安装包已生成
echo.

echo ============================================
echo  构建完成！
echo  安装包在: %PROJECT_ROOT%\dist-electron\
echo ============================================
pause
