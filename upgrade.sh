#!/bin/bash
# SonettoHere - Config Upgrade (macOS / Linux)
# 等价于 Windows 下的 upgrade.bat，核心逻辑由 upgrade.py 完成。
cd "$(dirname "$0")"

echo "========================================"
echo "  SonettoHere - Config Upgrade"
echo "========================================"
echo

if [ ! -f main.py ]; then
    echo "[ERR] Run this script from the project root."
    exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
    echo "[ERR] Virtual environment not found. Run ./setup.sh first."
    exit 1
fi

echo "[1/2] Pulling updates and running migrations ..."
".venv/bin/python" upgrade.py
EXIT_CODE=$?

echo
echo "========================================"
if [ $EXIT_CODE -ne 0 ]; then
    echo "  Result: [FAILED] Check the log above."
else
    echo "  Result: [OK]"
fi
echo "========================================"
echo
