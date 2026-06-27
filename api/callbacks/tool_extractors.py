"""工具输出数据提取器 — 每个工具对应一个独立 Strategy 函数。

通过 Registry 模式将 _extract_tool_data 中的 if-elif 分支链分解为独立的提取器函数。
"""

import ast
from collections.abc import Callable
from typing import Any

# ── Types ──────────────────────────────────────────────────────────────

Handler = Callable[[str, dict[str, Any], str | None], dict[str, Any] | None]
"""提取器签名：(tool_name, parsed, tool_input) → 前端数据 dict 或 None。"""

# ── Registry ───────────────────────────────────────────────────────────

_REGISTRY: dict[str, Handler] = {}
_PREFIX_REGISTRY: list[tuple[str, Handler]] = []

def register(tool_name: str) -> Callable[[Handler], Handler]:
    """精确匹配注册装饰器。"""

    def decorator(fn: Handler) -> Handler:
        _REGISTRY[tool_name] = fn
        return fn

    return decorator

def register_prefix(prefix: str) -> Callable[[Handler], Handler]:
    """前缀匹配注册装饰器（如 todo_*）。"""

    def decorator(fn: Handler) -> Handler:
        _PREFIX_REGISTRY.append((prefix, fn))
        return fn

    return decorator

# ── Dispatch ───────────────────────────────────────────────────────────

def _dispatch(
    tool_name: str, parsed: dict[str, Any], tool_input: str | None = None
) -> dict[str, Any] | None:
    handler = _REGISTRY.get(tool_name)
    if handler:
        return handler(tool_name, parsed, tool_input)

    for prefix, handler in _PREFIX_REGISTRY:
        if tool_name.startswith(prefix):
            return handler(tool_name, parsed, tool_input)

    return None

# ── Helper ─────────────────────────────────────────────────────────────

def _get_data(parsed: dict[str, Any]) -> dict[str, Any] | None:
    """提取 parsed['data'] 并校验为 dict。success=false 时视为错误返回 None。"""
    if parsed.get("success") is False:
        return None
    data = parsed.get("data", {})
    return data if isinstance(data, dict) else None

# ═══════════════════════════════════════════════════════════════════════
# 工具提取器
# ═══════════════════════════════════════════════════════════════════════

# ── Todo 系列 ──────────────────────────────────────────────────────────

@register("todo_list")
def _extract_todo_list(
    _tool_name: str,
    parsed: dict[str, Any],
    _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 tool_type=task_list, total, tasks。"""
    data = _get_data(parsed)
    if data is None:
        return None
    result: dict[str, Any] = {"tool_type": "task_list"}
    result["total"] = data.get("total")
    tasks = data.get("tasks", [])
    if isinstance(tasks, list):
        result["tasks"] = tasks
    return result

@register("todo_list_projects")
def _extract_todo_projects(
    _tool_name: str,
    parsed: dict[str, Any],
    _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 tool_type=project_list, total, projects。"""
    data = _get_data(parsed)
    if data is None:
        return None
    result: dict[str, Any] = {"tool_type": "project_list"}
    result["total"] = data.get("total")
    projects = data.get("projects", [])
    if isinstance(projects, list):
        result["projects"] = projects
    return result

@register("todo_list_sections")
def _extract_todo_sections(
    _tool_name: str,
    parsed: dict[str, Any],
    _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 total, sections（含 project_name 上下文）。"""
    data = _get_data(parsed)
    if data is None:
        return None
    result: dict[str, Any] = {}
    result["total"] = data.get("total")
    sections = data.get("sections", [])
    if isinstance(sections, list):
        result["sections"] = sections
        if sections and not result.get("project_name"):
            result["project_name"] = sections[0].get("project_name")
    return result if result.get("sections") is not None else None

@register("todo_list_labels")
def _extract_todo_labels(
    _tool_name: str,
    parsed: dict[str, Any],
    _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 total, labels。"""
    data = _get_data(parsed)
    if data is None:
        return None
    result: dict[str, Any] = {}
    result["total"] = data.get("total")
    labels = data.get("labels", [])
    if isinstance(labels, list):
        result["labels"] = labels
    return result if result.get("labels") is not None else None

@register_prefix("todo_")
def _extract_todo_generic(
    tool_name: str,
    parsed: dict[str, Any],
    _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 tool_type=single_task, task_id, content, due_date, priority, project, message, is_completed。"""
    data = _get_data(parsed)
    if data is None:
        return None
    result: dict[str, Any] = {"tool_type": "single_task"}
    for field in (
        "task_id",
        "content",
        "due_date",
        "priority",
        "project",
        "message",
        "is_completed",
    ):
        if field in data:
            result[field] = data[field]
    return result

# ── Task Tracker ───────────────────────────────────────────────────────

@register("task_tracker")
def _extract_task_tracker(
    _tool_name: str,
    parsed: dict[str, Any],
    _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 tool_type, total, pending, in_progress, completed, current_task, todos。"""
    data = _get_data(parsed)
    if data is None:
        return None
    result: dict[str, Any] = {
        "tool_type": "task_tracker",
        "total": data.get("total"),
        "pending": data.get("pending"),
        "in_progress": data.get("in_progress"),
        "completed": data.get("completed"),
        "current_task": data.get("current_task"),
    }
    todos = data.get("todos")
    if isinstance(todos, list):
        result["todos"] = todos
    return result

# ── Python 执行 ────────────────────────────────────────────────────────

@register("run_python")
def _extract_run_python(
    _tool_name: str,
    parsed: dict[str, Any],
    tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 tool_type, stdout, code。"""
    data = _get_data(parsed)
    if data is None:
        return None
    result: dict[str, Any] = {
        "tool_type": "run_python",
        "stdout": data.get("output", ""),
    }
    if tool_input:
        try:
            input_parsed = ast.literal_eval(tool_input)
        except (ValueError, SyntaxError, TypeError):
            pass
        else:
            if isinstance(input_parsed, dict):
                code = input_parsed.get("code", "")
                if isinstance(code, str) and code:
                    result["code"] = code
    return result

# ── 文件读取 ────────────────────────────────────────────────────────────

@register("file_read")
def _extract_file_read(
    _tool_name: str,
    parsed: dict[str, Any],
    _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 read_file 的数据字段。"""
    data = _get_data(parsed)
    if data is None:
        return None

    file_path = data.get("file_path", "")
    content = data.get("content", "")
    file_info = data.get("file_info", {})
    return {
        "operation": "read_file",
        "file_path": file_path,
        "file_name": file_path.split("/")[-1].split("\\")[-1] or "unknown",
        "size_bytes": file_info.get("size", 0),
        "line_count": content.count("\n") + 1 if isinstance(content, str) else 0,
        "content": content,
    }


# ── 文件写入 ────────────────────────────────────────────────────────────

@register("file_write")
def _extract_file_write(
    _tool_name: str,
    parsed: dict[str, Any],
    _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 write_file 的数据字段。"""
    data = _get_data(parsed)
    if data is None:
        return None

    file_path = data.get("file_path", "")
    return {
        "operation": "write_file",
        "file_path": file_path,
        "file_name": file_path.split("/")[-1].split("\\")[-1] or "unknown",
        "size_bytes": data.get("size", 0),
        "line_count": data.get("line_count", data.get("size", 0)),
        "success": True,
    }


# ── 文件管理 ────────────────────────────────────────────────────────────

@register("file_manage")
def _extract_file_manage(
    _tool_name: str,
    parsed: dict[str, Any],
    tool_input: str | None = None,
) -> dict[str, Any] | None:
    """按 operation (delete_file / rename_file / create_directory) 返回不同字段。"""
    data = _get_data(parsed)
    if data is None:
        return None

    operation = ""
    if tool_input:
        try:
            input_parsed = ast.literal_eval(tool_input)
        except (ValueError, SyntaxError, TypeError):
            pass
        else:
            if isinstance(input_parsed, dict):
                operation = str(input_parsed.get("operation", "") or "")

    if operation == "delete_file":
        return {
            "operation": "delete_file",
            "file_path": data.get("file_path", ""),
            "message": data.get("message", ""),
        }

    if operation == "rename_file":
        return {
            "operation": "rename_file",
            "file_path": data.get("old_path", data.get("file_path", "")),
            "new_path": data.get("new_path", ""),
            "message": data.get("message", ""),
        }

    if operation == "create_directory":
        return {
            "operation": "create_directory",
            "directory_path": data.get("directory_path", ""),
            "message": data.get("message", ""),
        }

    return None


# ── 文件搜索 ────────────────────────────────────────────────────────────

@register("file_search")
def _extract_file_search(
    _tool_name: str,
    parsed: dict[str, Any],
    tool_input: str | None = None,
) -> dict[str, Any] | None:
    """按 operation (list_directory / search_files) 返回不同字段。"""
    data = _get_data(parsed)
    if data is None:
        return None

    operation = ""
    if tool_input:
        try:
            input_parsed = ast.literal_eval(tool_input)
        except (ValueError, SyntaxError, TypeError):
            pass
        else:
            if isinstance(input_parsed, dict):
                operation = str(input_parsed.get("operation", "") or "")

    if operation == "list_directory":
        directory = data.get("directory", "")
        items_raw = data.get("items", [])
        items = []
        for item in items_raw if isinstance(items_raw, list) else []:
            items.append({
                "name": item.get("name", ""),
                "type": "directory" if item.get("is_dir") else "file",
                "size_bytes": item.get("size", 0),
            })
        return {
            "operation": "list_directory",
            "directory_path": directory,
            "total_items": data.get("count", len(items)),
            "items": items,
        }

    if operation == "search_files":
        directory = data.get("search_directory", "")
        items_raw = data.get("found_files", [])
        items = []
        for item in items_raw if isinstance(items_raw, list) else []:
            items.append({
                "name": item.get("name", ""),
                "type": "directory" if item.get("is_dir") else "file",
                "size_bytes": item.get("size", 0),
            })
        return {
            "operation": "search_files",
            "search_directory": directory,
            "total_items": data.get("count", len(items)),
            "items": items,
        }

    return None


# ── 文件精确编辑 ────────────────────────────────────────────────────────

@register("file_edit")
def _extract_file_edit(
    _tool_name: str,
    parsed: dict[str, Any],
    tool_input: str | None = None,
) -> dict[str, Any] | None:
    """按 operation 返回不同字段：edit → old/new/replaced_count；read → lines；search → matches。"""
    data = _get_data(parsed)
    if data is None:
        return None

    operation = ""
    if tool_input:
        try:
            input_parsed = ast.literal_eval(tool_input)
        except (ValueError, SyntaxError, TypeError):
            pass
        else:
            if isinstance(input_parsed, dict):
                operation = str(input_parsed.get("operation", "") or "")

    if operation == "edit":
        return {
            "operation": "edit",
            "file_path": data.get("file_path", ""),
            "replaced_count": data.get("replaced_count", 0),
            "replace_all": data.get("replace_all", False),
            "message": data.get("message", ""),
        }

    if operation == "read":
        lines = data.get("lines", [])
        return {
            "operation": "read",
            "file_path": data.get("file_path", ""),
            "total_lines": data.get("total_lines", 0),
            "offset": data.get("offset", 0),
            "content": data.get("content", ""),
            "line_count": len(lines),
            "lines": lines,
        }

    if operation == "multi_edit":
        results = data.get("results", [])
        return {
            "operation": "multi_edit",
            "file_path": data.get("file_path", ""),
            "total_edits": data.get("total_edits", 0),
            "success_count": data.get("success_count", 0),
            "failed_count": data.get("failed_count", 0),
            "results": results,
        }

    if operation == "search":
        matches = data.get("matches", [])
        return {
            "operation": "search",
            "file_path": data.get("file_path", ""),
            "pattern": data.get("pattern", ""),
            "total_matches": data.get("total_matches", 0),
            "matches": matches,
        }

    return None

# ── 塔罗占卜 ───────────────────────────────────────────────────────────

@register("tarot")
def _extract_tarot(
    _tool_name: str,
    parsed: dict[str, Any],
    _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 tool_type, question, spread_type, spread_name, cards_count, cards。"""
    data = _get_data(parsed)
    if data is None:
        return None
    cards_raw = data.get("cards", [])
    cards = []
    if isinstance(cards_raw, list):
        for card in cards_raw:
            if not isinstance(card, dict):
                continue
            cards.append(
                {
                    "name": card.get("name", ""),
                    "name_en": card.get("name_en", ""),
                    "suit": card.get("suit", ""),
                    "element": card.get("element", ""),
                    "keywords": card.get("keywords", []),
                    "position": card.get("position", ""),
                    "status": card.get("status", ""),
                    "meaning": card.get("meaning", []),
                    "description": card.get("description", ""),
                }
            )
    return {
        "tool_type": "tarot",
        "question": data.get("question", ""),
        "spread_type": data.get("spread_type", ""),
        "spread_name": data.get("spread_name", ""),
        "cards_count": data.get("cards_count", len(cards)),
        "cards": cards,
    }

# ── 地图系列 ───────────────────────────────────────────────────────────

@register("nearby_search")
@register("fuzzy_address_search")
def _extract_map_search(
    tool_name: str,
    parsed: dict[str, Any],
    _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 count, pois；nearby_search 额外返回 location/radius, fuzzy_address_search 额外返回 city。"""
    data = _get_data(parsed)
    if data is None:
        return None
    pois_raw = data.get("pois", [])
    pois = []
    if isinstance(pois_raw, list):
        for poi in pois_raw:
            if not isinstance(poi, dict):
                continue
            pois.append(
                {
                    "name": poi.get("name", ""),
                    "address": poi.get("address", ""),
                    "location": poi.get("location", ""),
                    "cityname": poi.get("cityname", ""),
                    "adname": poi.get("adname", ""),
                    "type": poi.get("type", ""),
                }
            )
    result = {
        "count": data.get("count", len(pois)),
        "pois": pois,
    }
    if tool_name == "nearby_search":
        result["location"] = data.get("location", "")
        result["keywords"] = data.get("keywords", "")
        result["radius"] = data.get("radius", 0)
    else:
        result["keywords"] = data.get("keywords", "")
        result["city"] = data.get("city", "")
    return result

@register("geocode_address")
def _extract_geocode(
    _tool_name: str,
    parsed: dict[str, Any],
    _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 address, location。"""
    data = _get_data(parsed)
    if data is None:
        return None
    return {
        "address": data.get("address", ""),
        "location": data.get("location", ""),
    }

@register("get_transit_route")
def _extract_transit_route(
    _tool_name: str,
    parsed: dict[str, Any],
    _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 origin, destination, origin_city, destination_city, route_count, routes。"""
    data = _get_data(parsed)
    if data is None:
        return None
    routes_raw = data.get("routes", [])
    routes = []
    if isinstance(routes_raw, list):
        for route in routes_raw:
            if not isinstance(route, dict):
                continue
            segments = []
            for seg in route.get("segments", []):
                if not isinstance(seg, dict):
                    continue
                seg_info: dict[str, Any] = {}
                walking = seg.get("walking")
                if isinstance(walking, dict):
                    seg_info["walking"] = {
                        "distance": walking.get("distance", 0),
                    }
                bus = seg.get("bus")
                if isinstance(bus, dict):
                    lines = []
                    for line in bus.get("lines", []):
                        if not isinstance(line, dict):
                            continue
                        lines.append(
                            {
                                "type": line.get("type", ""),
                                "name": line.get("name", ""),
                                "departure_stop": line.get("departure_stop", ""),
                                "arrival_stop": line.get("arrival_stop", ""),
                                "via_num": line.get("via_num", 0),
                                "distance": line.get("distance", 0),
                                "duration": line.get("duration", 0),
                            }
                        )
                    seg_info["bus"] = {"lines": lines}
                segments.append(seg_info)
            routes.append(
                {
                    "cost": route.get("cost", 0),
                    "duration": route.get("duration", 0),
                    "walking_distance": route.get("walking_distance", 0),
                    "segments": segments,
                }
            )
    return {
        "origin": data.get("origin", ""),
        "destination": data.get("destination", ""),
        "origin_city": data.get("origin_city", ""),
        "destination_city": data.get("destination_city", ""),
        "route_count": data.get("route_count", len(routes)),
        "routes": routes,
    }

@register("get_cycling_route")
def _extract_cycling_route(
    _tool_name: str,
    parsed: dict[str, Any],
    _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 origin, destination, path_count, paths。"""
    data = _get_data(parsed)
    if data is None:
        return None
    paths_raw = data.get("paths", [])
    paths = []
    if isinstance(paths_raw, list):
        for path in paths_raw:
            if not isinstance(path, dict):
                continue
            steps = []
            for step in path.get("steps", []):
                if not isinstance(step, dict):
                    continue
                steps.append(
                    {
                        "instruction": step.get("instruction", ""),
                        "orientation": step.get("orientation", ""),
                        "road": step.get("road", ""),
                        "distance": step.get("distance", 0),
                        "duration": step.get("duration", 0),
                    }
                )
            paths.append(
                {
                    "distance": path.get("distance", 0),
                    "duration": path.get("duration", 0),
                    "steps": steps,
                }
            )
    return {
        "origin": data.get("origin", ""),
        "destination": data.get("destination", ""),
        "path_count": data.get("path_count", len(paths)),
        "paths": paths,
    }

# ── 天气查询 ───────────────────────────────────────────────────────────

@register("get_current_weather")
def _extract_weather(
    _tool_name: str,
    parsed: dict[str, Any],
    _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 city, temp, condition, humidity, wind；可选 temp_feel, visibility, pressure, forecast。"""
    data = _get_data(parsed)
    if data is None:
        return None

    def _fmt_temp(val: Any) -> str:
        if isinstance(val, (int, float)):
            return f"{val}°C"
        return str(val) if val else ""

    temp_val = data.get("temperature")
    temp_str = _fmt_temp(temp_val)
    humidity_val = data.get("humidity")
    humidity_str = (
        f"{humidity_val}%"
        if isinstance(humidity_val, (int, float))
        else str(humidity_val)
        if humidity_val
        else ""
    )
    wind_parts = []
    if data.get("wind_direction"):
        wind_parts.append(data["wind_direction"])
    if data.get("wind_power"):
        wind_parts.append(data["wind_power"])
    wind_str = " ".join(wind_parts)
    result: dict[str, Any] = {
        "city": data.get("city", ""),
        "temp": temp_str,
        "condition": data.get("weather", ""),
        "humidity": humidity_str,
        "wind": wind_str,
    }
    if "report_time" in data:
        result["update_time"] = data["report_time"]
    if "feels_like" in data:
        feels = data["feels_like"]
        result["temp_feel"] = _fmt_temp(feels)
    if "visibility" in data:
        result["visibility"] = f"{data['visibility']}km"
    if "pressure" in data:
        result["pressure"] = f"{data['pressure']}hPa"
    if "aqi" in data:
        result["aqi"] = data["aqi"]
    if "aqi_level" in data:
        result["aqi_level"] = data["aqi_level"]
    if "aqi_category" in data:
        result["aqi_category"] = data["aqi_category"]
    if "aqi_primary" in data:
        result["aqi_primary"] = data["aqi_primary"]
    if "uv" in data:
        result["uv"] = data["uv"]
    if "cloud" in data:
        result["cloud"] = f"{data['cloud']}%"
    alerts = data.get("alerts")
    if isinstance(alerts, list) and len(alerts) > 0:
        result["alerts"] = [
            {
                "title": a.get("title", ""),
                "type": a.get("type", ""),
                "level": a.get("level", ""),
                "text": a.get("text", ""),
                "publish_time": a.get("publish_time", ""),
                "publisher": a.get("publisher", ""),
                "guidance": a.get("guidance", ""),
            }
            for a in alerts
            if isinstance(a, dict)
        ]
    forecast = data.get("forecast")
    if isinstance(forecast, list):
        result["forecast"] = [
            {
                "day": d.get("date", d.get("week", "")),
                "high": _fmt_temp(d.get("temp_max", "")),
                "low": _fmt_temp(d.get("temp_min", "")),
                "condition": d.get("weather_day", d.get("weather_night", "")),
                "sunrise": d.get("sunrise", ""),
                "sunset": d.get("sunset", ""),
                "pop": f"{d['pop']}%" if isinstance(d.get("pop"), (int, float)) else str(d.get("pop", "")) if d.get("pop") else "",
                "humidity": f"{d['humidity']}%" if isinstance(d.get("humidity"), (int, float)) else str(d.get("humidity", "")) if d.get("humidity") else "",
            }
            for d in forecast
            if isinstance(d, dict)
        ]

    # ── 逐小时预报（已提取，UI 暂未渲染） ──
    hourly = data.get("hourly_forecast")
    if isinstance(hourly, list):
        result["hourly_forecast"] = [
            {
                "time": h.get("time", ""),
                "temperature": str(h.get("temperature", "")),
                "weather": h.get("weather", ""),
                "wind_direction": h.get("wind_direction", ""),
                "wind_speed": str(h.get("wind_speed", "")),
                "humidity": str(h.get("humidity", "")),
                "pop": f"{h['pop']}%" if isinstance(h.get("pop"), (int, float)) else str(h.get("pop", "")),
            }
            for h in hourly
            if isinstance(h, dict)
        ]

    # ── 分钟级降水（已提取，UI 暂未渲染） ──
    if "minutely_precip" in data:
        result["minutely_precip"] = data["minutely_precip"]
    if "minutely_forecast" in data:
        result["minutely_forecast"] = data["minutely_forecast"]

    # ── 生活指数（已提取，UI 暂未渲染） ──
    if "life_indices" in data:
        result["life_indices"] = data["life_indices"]

    return result

# ── 图片理解 ───────────────────────────────────────────────────────────

@register("analyze_image")
def _extract_analyze_image(
    _tool_name: str,
    parsed: dict[str, Any],
    _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 tool_type, response。"""
    data = _get_data(parsed)
    if data is None:
        return None
    return {
        "tool_type": "analyze_image",
        "response": data.get("response", ""),
    }

# ── 节假日查询 ─────────────────────────────────────────────────────────

@register("holiday_calendar")
def _extract_holiday(
    _tool_name: str,
    parsed: dict[str, Any],
    _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 mode, date/month/year, 统计字段, days, holidays, nearby。"""
    data = _get_data(parsed)
    if data is None:
        return None
    result: dict[str, Any] = {"mode": data.get("mode", "")}

    query = data.get("query")
    if isinstance(query, dict):
        for field in ("date", "month", "year"):
            if query.get(field):
                result[field] = query[field]

    summary = data.get("summary")
    if isinstance(summary, dict):
        for field in (
            "total_days",
            "holiday_events",
            "rest_days",
            "legal_rest_days",
            "workdays",
        ):
            if field in summary:
                result[field] = summary[field]

    days_raw = data.get("days", [])
    if isinstance(days_raw, list):
        result["days"] = [
            {
                "date": d.get("date", ""),
                "weekday": d.get("weekday_cn", ""),
                "lunar_date": f"{d.get('lunar_month_name', '')}{d.get('lunar_day_name', '')}",
                "lunar_month": d.get("lunar_month_name", ""),
                "lunar_day": d.get("lunar_day_name", ""),
                "legal_holiday_name": d.get("legal_holiday_name", ""),
                "solar_festival": d.get("solar_festival", ""),
                "lunar_festival": d.get("lunar_festival", ""),
                "solar_term": d.get("solar_term", ""),
                "is_rest_day": d.get("is_rest_day", False),
                "is_holiday": d.get("is_holiday", False),
                "ganzhi_year": d.get("ganzhi_year", ""),
                "ganzhi_month": d.get("ganzhi_month", ""),
                "ganzhi_day": d.get("ganzhi_day", ""),
            }
            for d in days_raw
            if isinstance(d, dict)
        ]
        first = result["days"][0] if result["days"] else None
        if first:
            result.setdefault("weekday", first["weekday"])
            if first["lunar_date"]:
                result["lunar_date"] = first["lunar_date"]
            if first["solar_term"]:
                result["solar_term"] = first["solar_term"]

    holidays = data.get("holidays", [])
    if isinstance(holidays, list):
        result["holidays"] = [
            {
                "name": h.get("name", ""),
                "type": h.get("type", ""),
                "date": h.get("date", ""),
            }
            for h in holidays
            if isinstance(h, dict)
        ]

    nearby = data.get("nearby")
    if isinstance(nearby, dict):
        nb: dict[str, Any] = {}
        for direction in ("previous", "next"):
            items = nearby.get(direction, [])
            if isinstance(items, list):
                nb[direction] = [
                    {
                        "date": item.get("date", ""),
                        "events": [
                            {
                                "name": e.get("name", ""),
                                "type": e.get("type", ""),
                                "date": e.get("date", ""),
                            }
                            for e in item.get("events", [])
                            if isinstance(e, dict)
                        ],
                    }
                    for item in items
                    if isinstance(item, dict)
                ]
        if nb:
            result["nearby"] = nb

    return result

# ── Tavily 搜索 ──────────────────────────────────────────────────────────

@register("tavily_search")
def _extract_tavily_search(
    _tool_name: str,
    parsed: dict[str, Any],
    _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 query, answer, results, response_time。"""
    data = _get_data(parsed)
    if data is None:
        return None

    results_raw = data.get("results", [])
    results = []
    if isinstance(results_raw, list):
        for item in results_raw:
            if not isinstance(item, dict):
                continue
            entry: dict[str, Any] = {
                "url": item.get("url", ""),
                "title": item.get("title", ""),
                "content": item.get("content", ""),
                "score": item.get("score", 0),
            }
            if "raw_content" in item and item["raw_content"]:
                entry["raw_content"] = item["raw_content"]
            if "published_date" in item:
                entry["published_date"] = item["published_date"]
            results.append(entry)

    return {
        "query": data.get("query", ""),
        "answer": data.get("answer", ""),
        "results": results,
        "response_time": data.get("response_time", 0),
    }

# ── Tavily 提取 ──────────────────────────────────────────────────────────

@register("tavily_extract")
def _extract_tavily_extract(
    _tool_name: str,
    parsed: dict[str, Any],
    _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 results（url, title, raw_content, images）, failed_results, response_time。"""
    data = _get_data(parsed)
    if data is None:
        return None

    results_raw = data.get("results", [])
    results = []
    if isinstance(results_raw, list):
        for item in results_raw:
            if not isinstance(item, dict):
                continue
            entry: dict[str, Any] = {
                "url": item.get("url", ""),
                "title": item.get("title", ""),
                "raw_content": item.get("raw_content", ""),
            }
            if "images" in item and isinstance(item["images"], list):
                entry["images"] = item["images"]
            results.append(entry)

    failed_raw = data.get("failed_results", [])
    failed_results = []
    if isinstance(failed_raw, list):
        for item in failed_raw:
            if not isinstance(item, dict):
                continue
            failed_results.append(
                {
                    "url": item.get("url", ""),
                    "error": item.get("error", ""),
                }
            )

    return {
        "results": results,
        "failed_results": failed_results,
        "response_time": data.get("response_time", 0),
    }

# ═══════════════════════════════════════════════════════════════════════
# 记忆 CRUD 工具系列
# ═══════════════════════════════════════════════════════════════════════

@register("list_memories")
def _extract_list_memories(
    _tool_name: str,
    parsed: dict[str, Any],
    _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 items（列表），count。"""
    data = _get_data(parsed)
    if data is None:
        return None
    result: dict[str, Any] = {}
    items = data.get("items")
    if isinstance(items, list):
        result["items"] = items
        result["count"] = len(items)
    return result if result else None

@register("read_memories")
def _extract_read_memories(
    _tool_name: str,
    parsed: dict[str, Any],
    _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回单条记忆的 id、description、theme，可选 history。"""
    data = _get_data(parsed)
    if data is None:
        return None
    result: dict[str, Any] = {}
    for key in ("id", "description", "theme", "history", "history_count", "formatted"):
        if key in data:
            result[key] = data[key]
    return result if result else None

@register("create_memory")
@register("update_memory")
@register("delete_memory")
@register("merge_memories")
def _extract_memory_generic(
    tool_name: str,
    parsed: dict[str, Any],
    _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 id / kept_id / removed_id, content, section, message。"""
    data = _get_data(parsed)
    if data is None:
        return None
    result: dict[str, Any] = {}
    for field in (
        "id",
        "kept_id",
        "removed_id",
        "content",
        "section",
        "message",
        "reason",
    ):
        if field in data:
            result[field] = data[field]
    return result if result else None
