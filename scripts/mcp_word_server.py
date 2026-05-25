"""
Office-Word-MCP-Server 包裝腳本。

原服務器啟動時會向 stdout 輸出日誌（"Loading configuration from .env file..." 等），
這些輸出會破壞 MCP stdio JSON-RPC 協議。
此包裝腳本將 print 重定向到 stderr，僅保留 MCP 框架的 stdout 通信。
"""

import sys
import builtins

# 將 print 重定向到 stderr，避免污染 stdout 的 MCP 協議通信
_original_print = builtins.print


def _stderr_print(*args, **kwargs):
    kwargs.setdefault("file", sys.stderr)
    _original_print(*args, **kwargs)


builtins.print = _stderr_print

from word_document_server.main import run_server

if __name__ == "__main__":
    run_server()
