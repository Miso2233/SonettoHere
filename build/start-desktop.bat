@echo off
chcp 65001 >nul
title SonettoHere Desktop (Dev Mode)

echo ============================================
echo  SonettoHere Desktop — 开发模式
echo ============================================
echo.

set PROJECT_ROOT=%~dp0..
set ELECTRON_DIR=%PROJECT_ROOT%\build\packaging\electron

echo 确保后端和前端在各自的终端中运行：
echo   后端: cd %PROJECT_ROOT% ^&^& .venv\Scripts\python main.py
echo   前端: cd %PROJECT_ROOT%\web ^&^& npm run dev
echo.
echo Electron 将连接到 http://localhost:5173
echo.

REM 检查 Electron 依赖
if not exist "%ELECTRON_DIR%\node_modules" (
    echo [setup] 安装 Electron 依赖...
    cd /d "%ELECTRON_DIR%"
    call npm ci
)

echo [启动] Electron...
cd /d "%ELECTRON_DIR%"
start "" node_modules\.bin\electron.cmd . --dev

echo Electron 已启动。
