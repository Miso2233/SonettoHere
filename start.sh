#!/bin/bash
# SonettoHere Startup (macOS / Linux)
# 等价于 Windows 下的 start.bat：启动后端 (FastAPI :8000) 与前端 (Vite :5173)，
# 等待就绪后打开浏览器。Ctrl+C 一并停止两个服务。
cd "$(dirname "$0")"

echo "========================================"
echo "  SonettoHere Startup"
echo "========================================"
echo

if [ ! -f main.py ]; then
    echo "[ERR] Run this script from the project root."
    exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
    echo "[ERR] Virtual env not found. Run:"
    echo "      ./setup.sh"
    exit 1
fi

if [ ! -d "web/node_modules" ]; then
    echo "[ERR] Frontend dependencies not found. Run:"
    echo "      ./setup.sh"
    exit 1
fi

cleanup() {
    echo
    echo "Stopping services ..."
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
    exit 0
}
trap cleanup INT TERM

echo "[1/3] Starting backend (FastAPI :8000) ..."
".venv/bin/python" main.py web &
BACKEND_PID=$!

echo "[2/3] Waiting for backend ..."
READY=0
for _ in $(seq 1 30); do
    if curl -s http://localhost:8000/api/health >/dev/null 2>&1; then
        READY=1
        break
    fi
    sleep 2
done

if [ "$READY" = "0" ]; then
    echo "       [WARN] Backend startup timed out, continuing ..."
else
    echo "       Backend ready."
fi

echo "[3/3] Starting frontend (Vite :5173) ..."
(
    cd web
    npm run dev
) &
FRONTEND_PID=$!

echo "       Waiting for frontend ..."
READY=0
for _ in $(seq 1 20); do
    if curl -s http://localhost:5173 >/dev/null 2>&1; then
        READY=1
        break
    fi
    sleep 2
done

# macOS 用 open，Linux 桌面环境回退到 xdg-open
open "http://localhost:5173" 2>/dev/null || xdg-open "http://localhost:5173" 2>/dev/null || true

echo
echo "========================================"
echo "  All services started"
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo "========================================"
echo
echo "Press Ctrl+C to stop both services."
echo

wait
