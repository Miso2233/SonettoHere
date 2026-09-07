"""OpenCode 网关请求头辅助。

OpenCode 网关（https://opencode.ai，含 "Console Go" / Zen 端点，如
``https://opencode.ai/zen/go/v1``）自 2026-09-06 起要求每个补全请求携带稳定的
``x-opencode-session`` 请求头，用于会话亲和路由（粘到同一后端实例以复用 KV/提示缓存）。
请求头缺失时网关退化为按客户端 IP 兜底路由，故此前表现为偶发的
``400 MissingSessionID``（"Request is missing x-opencode-session ..."）。

本模块对指向 OpenCode 网关的 base_url 生成该请求头；session id 在同一进程内
（按 base_url+api_key 键控）保持稳定。其它网关返回空 dict，不注入任何内容。
"""

import urllib.parse
import uuid

_OPENCODE_HOST_SUFFIX = ".opencode.ai"


def is_opencode_gateway(base_url: str) -> bool:
    """判断 base_url 是否指向 OpenCode 网关（host 为 opencode.ai 或子域）。"""
    if not base_url:
        return False
    try:
        host = (urllib.parse.urlparse(base_url).hostname or "").lower()
    except ValueError:
        return False
    return host == "opencode.ai" or host.endswith(_OPENCODE_HOST_SUFFIX)


# 每个 (base_url, api_key) 对应一个运行期稳定的 session id，reload/多次构造不变。
_session_ids: dict[tuple[str, str], str] = {}


def opencode_session_headers(base_url: str, api_key: str) -> dict[str, str]:
    """为 OpenCode 网关生成需附加的缺省请求头；非网关 URL 返回空 dict。

    Returns:
        ``{"x-opencode-session": "<运行期稳定 id>"}`` 或 ``{}``。
    """
    if not is_opencode_gateway(base_url):
        return {}
    key = (base_url.rstrip("/"), api_key)
    session_id = _session_ids.get(key)
    if session_id is None:
        session_id = uuid.uuid4().hex
        _session_ids[key] = session_id
    return {"x-opencode-session": session_id}