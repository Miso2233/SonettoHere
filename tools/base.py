"""工具（Tool）基类和共享 HTTP 客户端。"""

import json
import os
from pathlib import Path

import requests
from langchain_core.tools import BaseTool
from todoist_api_python.api import TodoistAPI
from uapi import UapiClient

from config.settings import get_settings


class SharedAPIClient:
    """所有 Tool 共享的 HTTP 客户端，API Key 仅加载一次。"""

    def __init__(self):
        settings = get_settings()
        self._session = requests.Session()
        self._uapi: UapiClient | None = None
        self._todoist: TodoistAPI | None = None
        self._amap_key = settings.amap_api_key
        self._uapis_key = settings.uapis_api_key
        self._todoist_token = settings.todoist_api_token

    @property
    def uapi(self) -> UapiClient:
        if self._uapi is None:
            self._uapi = UapiClient("https://uapis.cn", token=self._uapis_key)
        return self._uapi

    @property
    def todoist(self) -> TodoistAPI:
        if self._todoist is None:
            self._todoist = TodoistAPI(self._todoist_token)
        return self._todoist

    @property
    def amap_key(self) -> str:
        return self._amap_key

    def amap_request(self, endpoint: str, params: dict) -> dict:
        """发起高德地图 API 请求。"""
        params["key"] = self._amap_key
        resp = self._session.get(
            f"https://restapi.amap.com{endpoint}", params=params
        )
        resp.raise_for_status()
        return resp.json()

    def close(self):
        self._session.close()


class ToolBase(BaseTool):
    """所有 Tool 的基类。提供 get_doc 通用实现和统一错误格式。"""

    client: SharedAPIClient | None = None

    def _load_doc(self) -> str:
        """读取同目录下的 TOOL.md，作为领域知识返回给 LLM。"""
        import sys

        mod = sys.modules.get(self.__class__.__module__)
        if mod is not None and hasattr(mod, "__file__") and mod.__file__ is not None:
            tool_dir = Path(mod.__file__).parent
        else:
            tool_dir = Path(".")
        doc_path = tool_dir / "TOOL.md"
        if doc_path.exists():
            return doc_path.read_text(encoding="utf-8")
        return "（本 Tool 暂无文档）"


def format_success(data: dict) -> str:
    """统一成功响应格式。"""
    return json.dumps({"success": True, "data": data}, ensure_ascii=False)


def format_error(message: str) -> str:
    """统一错误响应格式。"""
    return json.dumps({"success": False, "error": message}, ensure_ascii=False)


def check_sonetto_blocker(target_path: str) -> str | None:
    """逐级检查路径的每一级目录是否包含 SonettoBlocker 文件（不区分大小写，不匹配后缀名）。

    从盘符根目录开始，依次检查每一层父目录中是否存在名为 "SonettoBlocker"
    的文件（任何扩展名均匹配）。一旦发现，返回该目录路径；否则返回 None。
    """
    if not target_path:
        return None

    abs_path = os.path.abspath(target_path)
    p = Path(abs_path)

    # 收集待检查的所有目录层级
    dirs_to_check: list[str] = []

    if p.is_dir():
        dirs_to_check.append(str(p))
    else:
        # 文件还不存在（如 write_file 写入新文件）则检查父目录
        parent = p.parent
        if parent:
            dirs_to_check.append(str(parent))

    # parents 从父目录向上直到根
    dirs_to_check.extend(str(parent) for parent in p.parents)

    # 从根向下逐级检查
    seen: set[str] = set()
    for dir_path in reversed(dirs_to_check):
        normalized = os.path.normpath(dir_path)
        if normalized in seen:
            continue
        seen.add(normalized)
        if not os.path.isdir(normalized):
            continue
        try:
            for entry in os.listdir(normalized):
                entry_name, _ = os.path.splitext(entry)
                if entry_name.lower() == "sonettoblocker":
                    # 返回友好的展示形式
                    return normalized
        except (PermissionError, OSError):
            continue

    return None
