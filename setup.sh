#!/bin/bash
# SonettoHere Setup (macOS / Linux)
# 等价于 Windows 下的 setup.bat，核心逻辑由 setup_guide.py 完成。
cd "$(dirname "$0")"

echo "========================================"
echo "  SonettoHere Setup"
echo "========================================"
echo

if [ ! -f main.py ]; then
    echo "[ERR] Please run this script from the project root."
    exit 1
fi

# macOS 通常只有 python3；Windows 才默认叫 python
if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "[ERR] Python not found. Please install Python 3.10+ first."
    echo "      Download: https://www.python.org/downloads/"
    exit 1
fi

"$PY" setup_guide.py
if [ $? -ne 0 ]; then
    exit 1
fi

echo
echo "Setup complete! You can now run ./start.sh"
echo
