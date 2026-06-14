"""工具（Tool）基类和共享 HTTP 客户端。"""

import json
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
