"""Const 固定会话 — YAML 持久化存储。

提供将会话状态（元数据 + 对话消息）序列化为 YAML 文件并重新加载的能力。
"""

import time
from pathlib import Path

import yaml

# api/const_session_store.py → api/data/const-sessions/
_CONST_DIR = Path(__file__).resolve().parent / "data" / "const-sessions"


def _ensure_dir() -> Path:
    _CONST_DIR.mkdir(parents=True, exist_ok=True)
    return _CONST_DIR


# ── 消息序列化 ─────────────────────────────────────────────────


def serialize_messages(raw_messages: list) -> list[dict]:
    """将 LangChain BaseMessage 对象列表转为可序列化的纯 dict 列表。"""
    result = []
    for msg in raw_messages:
        entry: dict = {
            "type": getattr(msg, "type", "unknown"),
            "content": msg.content if hasattr(msg, "content") else str(msg),
        }
        if hasattr(msg, "tool_call_id") and msg.tool_call_id:
            entry["tool_call_id"] = msg.tool_call_id
        if hasattr(msg, "name") and msg.name:
            entry["name"] = msg.name
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            entry["tool_calls"] = msg.tool_calls
        if hasattr(msg, "additional_kwargs") and msg.additional_kwargs:
            entry["additional_kwargs"] = msg.additional_kwargs
        result.append(entry)
    return result


def deserialize_messages(data: list[dict]) -> list:
    """将纯 dict 列表重建为 LangChain BaseMessage 对象。"""
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    reconstructed = []
    for m in data:
        msg_type = m.get("type", "human")
        content = m.get("content", "")
        match msg_type:
            case "human":
                reconstructed.append(HumanMessage(content=content))
            case "ai":
                kwargs: dict = {"content": content}
                if "tool_calls" in m:
                    kwargs["tool_calls"] = m["tool_calls"]
                if "additional_kwargs" in m:
                    kwargs["additional_kwargs"] = m["additional_kwargs"]
                reconstructed.append(AIMessage(**kwargs))
            case "tool":
                reconstructed.append(ToolMessage(
                    content=content,
                    tool_call_id=m.get("tool_call_id", ""),
                    name=m.get("name", ""),
                ))
            case _:
                # fallback: treat as human message
                reconstructed.append(HumanMessage(content=content))
    return reconstructed


# ── 文件 I/O ──────────────────────────────────────────────────


def save_const_session(
    session_id: str,
    const_name: str,
    metadata: dict,
    messages: list[dict],
) -> str:
    """将会话持久化为 YAML 文件。

    Returns:
        写入的文件路径。
    """
    ensure_dir = _ensure_dir()
    data = {
        "session_id": session_id,
        "const_name": const_name,
        "const_saved_at": time.time(),
        "metadata": metadata,
        "messages": messages,
    }
    filepath = ensure_dir / f"{session_id}.yaml"
    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    return str(filepath)


def load_const_session(filepath: Path) -> dict | None:
    """加载单个 const 会话 YAML 文件。"""
    try:
        with open(filepath, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def load_all_const_sessions() -> list[dict]:
    """扫描 const-sessions/ 目录，加载所有 YAML。"""
    ensure_dir = _ensure_dir()
    sessions = []
    for fpath in sorted(ensure_dir.glob("*.yaml")):
        data = load_const_session(fpath)
        if data and data.get("session_id"):
            sessions.append(data)
    return sessions


def delete_const_session(session_id: str) -> bool:
    """删除 const 会话文件。"""
    filepath = _CONST_DIR / f"{session_id}.yaml"
    if filepath.exists():
        filepath.unlink()
        return True
    return False
