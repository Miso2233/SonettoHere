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

def _dispatch(tool_name: str, parsed: dict[str, Any],
              tool_input: str | None = None) -> dict[str, Any] | None:
    handler = _REGISTRY.get(tool_name)
    if handler:
        return handler(tool_name, parsed, tool_input)

    for prefix, handler in _PREFIX_REGISTRY:
        if tool_name.startswith(prefix):
            return handler(tool_name, parsed, tool_input)

    return None


# ── Helper ─────────────────────────────────────────────────────────────

def _get_data(parsed: dict[str, Any]) -> dict[str, Any] | None:
    """提取 parsed['data'] 并校验为 dict。"""
    data = parsed.get("data", {})
    return data if isinstance(data, dict) else None


# ═══════════════════════════════════════════════════════════════════════
# 工具提取器
# ═══════════════════════════════════════════════════════════════════════

# ── Bilibili 下载 ──────────────────────────────────────────────────────

@register("bilibili_download")
def _extract_bilibili(
    _tool_name: str, parsed: dict[str, Any], _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 video_title, cover_url, file_path, quality。"""
    data = _get_data(parsed)
    if data is None:
        return None
    cover_path = data.get("cover_path", "")
    return {
        "video_title": data.get("title"),
        "cover_url": f"/api/file?path={cover_path}" if cover_path else None,
        "file_path": data.get("file_path"),
        "quality": data.get("quality"),
    }


# ── Todo 系列 ──────────────────────────────────────────────────────────

@register("todo_list")
def _extract_todo_list(
    _tool_name: str, parsed: dict[str, Any], _tool_input: str | None = None,
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
    _tool_name: str, parsed: dict[str, Any], _tool_input: str | None = None,
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


@register_prefix("todo_")
def _extract_todo_generic(
    tool_name: str, parsed: dict[str, Any], _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 tool_type=single_task, task_id, content, due_date, priority, project, message, is_completed。"""
    data = _get_data(parsed)
    if data is None:
        return None
    result: dict[str, Any] = {"tool_type": "single_task"}
    for field in ("task_id", "content", "due_date", "priority",
                  "project", "message", "is_completed"):
        if field in data:
            result[field] = data[field]
    return result


# ── Task Tracker ───────────────────────────────────────────────────────

@register("task_tracker")
def _extract_task_tracker(
    _tool_name: str, parsed: dict[str, Any], _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 tool_type, status, total_steps, current_step, current_task, tasks, message。"""
    data = _get_data(parsed)
    if data is None:
        return None
    result: dict[str, Any] = {
        "tool_type": "task_tracker",
        "status": data.get("status"),
        "total_steps": data.get("total_steps"),
        "current_step": data.get("current_step"),
        "current_task": data.get("current_task"),
    }
    tasks = data.get("tasks")
    if isinstance(tasks, list):
        result["tasks"] = tasks
    if "message" in data:
        result["message"] = data["message"]
    return result


# ── Python 执行 ────────────────────────────────────────────────────────

@register("run_python")
def _extract_run_python(
    _tool_name: str, parsed: dict[str, Any], tool_input: str | None = None,
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


# ── 文件操作 ────────────────────────────────────────────────────────────

@register("file_operations")
def _extract_file_operations(
    _tool_name: str, parsed: dict[str, Any], tool_input: str | None = None,
) -> dict[str, Any] | None:
    """按 operation (read_file / write_file / list_directory / search_files) 返回不同字段。"""
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

    if operation == "read_file":
        file_path = data.get("file_info", {}).get("path", "")
        content = data.get("content", "")
        size = data.get("file_info", {}).get("size", 0)
        return {
            "operation": "read_file",
            "file_path": file_path,
            "file_name": file_path.split("/")[-1].split("\\")[-1] or "unknown",
            "size_bytes": size,
            "line_count": content.count("\n") + 1 if isinstance(content, str) else 0,
            "content": content,
        }

    if operation == "write_file":
        file_path = data.get("file_path", "")
        size = data.get("size", 0)
        return {
            "operation": "write_file",
            "file_path": file_path,
            "file_name": file_path.split("/")[-1].split("\\")[-1] or "unknown",
            "size_bytes": size,
            "line_count": size,
            "success": True,
        }

    if operation in ("list_directory",):
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
    _tool_name: str, parsed: dict[str, Any], tool_input: str | None = None,
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
    _tool_name: str, parsed: dict[str, Any], _tool_input: str | None = None,
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
            cards.append({
                "name": card.get("name", ""),
                "name_en": card.get("name_en", ""),
                "suit": card.get("suit", ""),
                "element": card.get("element", ""),
                "keywords": card.get("keywords", []),
                "position": card.get("position", ""),
                "status": card.get("status", ""),
                "meaning": card.get("meaning", []),
                "description": card.get("description", ""),
            })
    return {
        "tool_type": "tarot",
        "question": data.get("question", ""),
        "spread_type": data.get("spread_type", ""),
        "spread_name": data.get("spread_name", ""),
        "cards_count": data.get("cards_count", len(cards)),
        "cards": cards,
    }


# ── 答案之书 ───────────────────────────────────────────────────────────

@register("answer_book")
def _extract_answer_book(
    _tool_name: str, parsed: dict[str, Any], _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 tool_type, question, answer。"""
    data = _get_data(parsed)
    if data is None:
        return None
    return {
        "tool_type": "answer_book",
        "question": data.get("question", ""),
        "answer": data.get("answer", ""),
    }


# ── 地图系列 ───────────────────────────────────────────────────────────

@register("nearby_search")
@register("fuzzy_address_search")
def _extract_map_search(
    tool_name: str, parsed: dict[str, Any], _tool_input: str | None = None,
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
            pois.append({
                "name": poi.get("name", ""),
                "address": poi.get("address", ""),
                "location": poi.get("location", ""),
                "cityname": poi.get("cityname", ""),
                "adname": poi.get("adname", ""),
                "type": poi.get("type", ""),
            })
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
    _tool_name: str, parsed: dict[str, Any], _tool_input: str | None = None,
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
    _tool_name: str, parsed: dict[str, Any], _tool_input: str | None = None,
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
                        lines.append({
                            "type": line.get("type", ""),
                            "name": line.get("name", ""),
                            "departure_stop": line.get("departure_stop", ""),
                            "arrival_stop": line.get("arrival_stop", ""),
                            "via_num": line.get("via_num", 0),
                            "distance": line.get("distance", 0),
                            "duration": line.get("duration", 0),
                        })
                    seg_info["bus"] = {"lines": lines}
                segments.append(seg_info)
            routes.append({
                "cost": route.get("cost", 0),
                "duration": route.get("duration", 0),
                "walking_distance": route.get("walking_distance", 0),
                "segments": segments,
            })
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
    _tool_name: str, parsed: dict[str, Any], _tool_input: str | None = None,
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
                steps.append({
                    "instruction": step.get("instruction", ""),
                    "orientation": step.get("orientation", ""),
                    "road": step.get("road", ""),
                    "distance": step.get("distance", 0),
                    "duration": step.get("duration", 0),
                })
            paths.append({
                "distance": path.get("distance", 0),
                "duration": path.get("duration", 0),
                "steps": steps,
            })
    return {
        "origin": data.get("origin", ""),
        "destination": data.get("destination", ""),
        "path_count": data.get("path_count", len(paths)),
        "paths": paths,
    }


# ── 天气查询 ───────────────────────────────────────────────────────────

@register("get_current_weather")
def _extract_weather(
    _tool_name: str, parsed: dict[str, Any], _tool_input: str | None = None,
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
    humidity_str = f"{humidity_val}%" if isinstance(humidity_val, (int, float)) else str(humidity_val) if humidity_val else ""
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
    if "feels_like" in data:
        feels = data["feels_like"]
        result["temp_feel"] = _fmt_temp(feels)
    if "visibility" in data:
        result["visibility"] = f'{data["visibility"]}km'
    if "pressure" in data:
        result["pressure"] = f'{data["pressure"]}hPa'
    forecast = data.get("forecast")
    if isinstance(forecast, list):
        result["forecast"] = [
            {
                "day": d.get("date", d.get("week", "")),
                "high": _fmt_temp(d.get("temp_max", "")),
                "low": _fmt_temp(d.get("temp_min", "")),
                "condition": d.get("weather_day", d.get("weather_night", "")),
            }
            for d in forecast if isinstance(d, dict)
        ]
    return result


# ── 时间查询 ───────────────────────────────────────────────────────────

@register("time_skill")
def _extract_time(
    _tool_name: str, parsed: dict[str, Any], _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 tool_type, datetime, date, time, weekday, timezone。"""
    data = _get_data(parsed)
    if data is None:
        return None
    return {
        "tool_type": "time",
        "datetime": data.get("datetime", ""),
        "date": data.get("date", ""),
        "time": data.get("time", ""),
        "weekday": data.get("weekday", ""),
        "timezone": data.get("timezone", ""),
    }


# ── 语法检查 ───────────────────────────────────────────────────────────

@register("syntax_checker")
def _extract_syntax_check(
    _tool_name: str, parsed: dict[str, Any], _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 tool_type, language, errors, warnings。"""
    data = _get_data(parsed)
    if data is None:
        return None
    return {
        "tool_type": "syntax_check",
        "language": data.get("language", ""),
        "errors": data.get("errors", []),
        "warnings": data.get("warnings", []),
    }


# ── B站 Cookie 设置 ────────────────────────────────────────────────────

@register("bilibili_set_cookie")
def _extract_set_cookie(
    _tool_name: str, parsed: dict[str, Any], _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 tool_type, message。"""
    data = _get_data(parsed)
    if data is None:
        return None
    return {
        "tool_type": "set_cookie",
        "message": data.get("message", ""),
    }


# ── 图片理解 ───────────────────────────────────────────────────────────

@register("analyze_image")
def _extract_analyze_image(
    _tool_name: str, parsed: dict[str, Any], _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 tool_type, response。"""
    data = _get_data(parsed)
    if data is None:
        return None
    return {
        "tool_type": "analyze_image",
        "response": data.get("response", ""),
    }


# ── 智能搜索 ───────────────────────────────────────────────────────────

@register("smart_search")
def _extract_smart_search(
    _tool_name: str, parsed: dict[str, Any], _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 query, total_results, results, sources, process_time_ms, metadata。"""
    data = _get_data(parsed)
    if data is None:
        return None

    results_raw = data.get("results", [])
    results = []
    if isinstance(results_raw, list):
        for item in results_raw:
            if not isinstance(item, dict):
                continue
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("snippet", ""),
                "domain": item.get("domain", ""),
                "source": item.get("source", ""),
                "position": item.get("position", 0),
                "score": item.get("score", 0),
                "publish_time": item.get("publish_time", ""),
            })

    sources_raw = data.get("sources", [])
    sources = []
    if isinstance(sources_raw, list):
        for src in sources_raw:
            if not isinstance(src, dict):
                continue
            sources.append({
                "name": src.get("name", ""),
                "status": src.get("status", ""),
                "result_count": src.get("result_count", 0),
                "elapsed_ms": src.get("elapsed_ms", 0),
                "first_result_host": src.get("first_result_host", ""),
            })

    return {
        "query": data.get("query", ""),
        "total_results": data.get("total_results", 0),
        "results": results,
        "sources": sources,
        "process_time_ms": data.get("process_time_ms", 0),
        "metadata": data.get("metadata"),
    }


# ── 节假日查询 ─────────────────────────────────────────────────────────

@register("holiday_calendar")
def _extract_holiday(
    _tool_name: str, parsed: dict[str, Any], _tool_input: str | None = None,
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
        for field in ("total_days", "holiday_events", "rest_days",
                       "legal_rest_days", "workdays"):
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
            for d in days_raw if isinstance(d, dict)
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
            for h in holidays if isinstance(h, dict)
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
                            for e in item.get("events", []) if isinstance(e, dict)
                        ],
                    }
                    for item in items if isinstance(item, dict)
                ]
        if nb:
            result["nearby"] = nb

    return result


# ── PDF 阅读 ───────────────────────────────────────────────────────────

@register("pdf_reader")
def _extract_pdf(
    _tool_name: str, parsed: dict[str, Any], tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 operation, file_path, file_size, page_count；可选 metadata, toc, text, page_range, query, results, total_matches, page_contents, total_pages。"""
    data = _get_data(parsed)
    if data is None:
        return None

    file_path = data.get("file_path", "") or ""
    if not file_path and tool_input:
        try:
            inp = ast.literal_eval(tool_input)
        except Exception:
            pass
        else:
            if isinstance(inp, dict):
                file_path = inp.get("file_path", "") or ""

    result: dict[str, Any] = {
        "operation": data.get("operation", ""),
        "file_path": file_path,
        "file_size": data.get("file_size", 0),
        "page_count": data.get("page_count", data.get("total_pages", 0)),
    }
    if "metadata" in data and isinstance(data["metadata"], dict):
        result["metadata"] = data["metadata"]
    if "toc" in data and isinstance(data["toc"], list):
        result["toc"] = data["toc"]
    if "text" in data:
        result["text"] = data["text"]
    if "page_range" in data:
        result["page_range"] = data["page_range"]
    if "query" in data:
        result["query"] = data["query"]
    if "results" in data and isinstance(data["results"], list):
        result["results"] = data["results"]
    if "total_matches" in data:
        result["total_matches"] = data["total_matches"]
    if "page_contents" in data and isinstance(data["page_contents"], dict):
        result["page_contents"] = data["page_contents"]
    if "total_pages" in data:
        result["total_pages"] = data["total_pages"]
    return result


# ── Word 文档阅读 ─────────────────────────────────────────────────────

@register("doc_reader")
def _extract_doc(
    _tool_name: str, parsed: dict[str, Any], tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 operation, file_path, file_size, paragraph_count, table_count；可选 metadata, paragraphs, paragraph_range, tables, text, query, results, total_matches, total_paragraphs。"""
    data = _get_data(parsed)
    if data is None:
        return None

    file_path = data.get("file_path", "") or ""
    if not file_path and tool_input:
        try:
            inp = ast.literal_eval(tool_input)
        except Exception:
            pass
        else:
            if isinstance(inp, dict):
                file_path = inp.get("file_path", "") or ""

    result: dict[str, Any] = {
        "operation": data.get("operation", ""),
        "file_path": file_path,
        "file_size": data.get("file_size", 0),
        "paragraph_count": data.get("paragraph_count", data.get("total_paragraphs", 0)),
        "table_count": data.get("table_count", 0),
    }
    if "metadata" in data and isinstance(data["metadata"], dict):
        result["metadata"] = data["metadata"]
    if "paragraphs" in data and isinstance(data["paragraphs"], list):
        result["paragraphs"] = data["paragraphs"]
    if "paragraph_range" in data:
        result["paragraph_range"] = data["paragraph_range"]
    if "tables" in data and isinstance(data["tables"], list):
        result["tables"] = data["tables"]
    if "text" in data:
        result["text"] = data["text"]
    if "query" in data:
        result["query"] = data["query"]
    if "results" in data and isinstance(data["results"], list):
        result["results"] = data["results"]
    if "total_matches" in data:
        result["total_matches"] = data["total_matches"]
    if "total_paragraphs" in data:
        result["total_paragraphs"] = data["total_paragraphs"]
    return result


# ── 代码质量分析 ───────────────────────────────────────────────────────

@register("code_quality_analyzer")
def _extract_code_quality(
    _tool_name: str, parsed: dict[str, Any], tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 file_path, analysis_type；可选 complexity, maintainability, duplication。"""
    data = _get_data(parsed)
    if data is None:
        return None

    file_path = ""
    analysis_type = ""
    if tool_input:
        try:
            inp = ast.literal_eval(tool_input)
        except Exception:
            pass
        else:
            if isinstance(inp, dict):
                file_path = inp.get("file_path", "") or ""
                analysis_type = inp.get("analysis_type", "") or ""

    result: dict[str, Any] = {
        "file_path": file_path,
        "analysis_type": analysis_type,
    }
    if "complexity" in data and isinstance(data["complexity"], dict):
        result["complexity"] = data["complexity"]
    if "maintainability" in data and isinstance(data["maintainability"], dict):
        result["maintainability"] = data["maintainability"]
    if "duplication" in data and isinstance(data["duplication"], dict):
        result["duplication"] = data["duplication"]
    return result


# ── 单元测试运行 ───────────────────────────────────────────────────────

@register("unit_test_runner")
def _extract_test_runner(
    _tool_name: str, parsed: dict[str, Any], _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 tests_run, failures, errors, skipped, successful, success_rate；可选 failures_details, errors_details。"""
    data = _get_data(parsed)
    if data is None:
        return None

    result: dict[str, Any] = {
        "tests_run": data.get("tests_run", 0),
        "failures": data.get("failures", 0),
        "errors": data.get("errors", 0),
        "skipped": data.get("skipped", 0),
        "successful": data.get("successful", 0),
        "success_rate": data.get("success_rate", 0.0),
    }
    if "failures_details" in data and isinstance(data["failures_details"], list):
        result["failures_details"] = data["failures_details"]
    if "errors_details" in data and isinstance(data["errors_details"], list):
        result["errors_details"] = data["errors_details"]
    return result


# ── 代码调试 ───────────────────────────────────────────────────────────

@register("debugger")
def _extract_debugger(
    _tool_name: str, parsed: dict[str, Any], _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """get_doc 模式返回 operation+content；其余返回 status/variables/output 或 status+error_type/error_message/traceback。"""
    raw_data = parsed.get("data")
    if isinstance(raw_data, str):
        return {"operation": "get_doc", "content": raw_data}
    if not isinstance(raw_data, dict):
        return None
    data = raw_data

    result: dict[str, Any] = {
        "status": data.get("status", ""),
    }
    if "variables" in data and isinstance(data["variables"], dict):
        result["variables"] = data["variables"]
    if data.get("status") == "success":
        result["output"] = data.get("output", "")
    else:
        if "error_type" in data:
            result["error_type"] = data["error_type"]
        if "error_message" in data:
            result["error_message"] = data["error_message"]
        if "traceback" in data:
            result["traceback"] = data["traceback"]
    return result


# ── 网页抓取 ───────────────────────────────────────────────────────────

@register("scrape_webpage")
def _extract_scrape(
    _tool_name: str, parsed: dict[str, Any], _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 url, title；可选 content, meta, open_graph, twitter_card, structured_data, headings, links, images, screenshot_base64。"""
    data = _get_data(parsed)
    if data is None:
        return None

    result: dict[str, Any] = {
        "url": data.get("url", ""),
        "title": data.get("title", ""),
    }
    if "content" in data:
        result["content"] = data["content"]
    if "meta" in data and isinstance(data["meta"], dict):
        result["meta"] = data["meta"]
    if "open_graph" in data and isinstance(data["open_graph"], dict):
        result["open_graph"] = data["open_graph"]
    if "twitter_card" in data and isinstance(data["twitter_card"], dict):
        result["twitter_card"] = data["twitter_card"]
    if "structured_data" in data and isinstance(data["structured_data"], list):
        result["structured_data"] = data["structured_data"]
    if "headings" in data and isinstance(data["headings"], list):
        result["headings"] = data["headings"]
    if "links" in data and isinstance(data["links"], list):
        result["links"] = data["links"]
    if "images" in data and isinstance(data["images"], list):
        result["images"] = data["images"]
    if "screenshot_base64" in data:
        result["screenshot_base64"] = data["screenshot_base64"]
    return result


# ═══════════════════════════════════════════════════════════════════════
# 记忆 CRUD 工具系列
# ═══════════════════════════════════════════════════════════════════════


@register("list_memories")
def _extract_list_memories(
    _tool_name: str, parsed: dict[str, Any], _tool_input: str | None = None,
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
    _tool_name: str, parsed: dict[str, Any], _tool_input: str | None = None,
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
    tool_name: str, parsed: dict[str, Any], _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 id / kept_id / removed_id, content, section, message。"""
    data = _get_data(parsed)
    if data is None:
        return None
    result: dict[str, Any] = {}
    for field in ("id", "kept_id", "removed_id", "content", "section", "message", "reason"):
        if field in data:
            result[field] = data[field]
    return result if result else None


# ═══════════════════════════════════════════════════════════════════════
# Word MCP 工具系列（word_* 前缀）
# ═══════════════════════════════════════════════════════════════════════

import re as _re

# ── 工具名 → 动作名映射 ──

_WORD_ACTION_MAP: dict[str, str] = {
    "create_document": "create_document",
    "copy_document": "copy_document",
    "merge_documents": "merge_documents",
    "get_document_info": "get_document_info",
    "get_document_text": "get_document_text",
    "get_document_outline": "get_document_outline",
    "list_available_documents": "list_documents",
    "get_document_xml": "get_document_xml",
    "add_paragraph": "add_paragraph",
    "add_heading": "add_heading",
    "add_table": "add_table",
    "add_picture": "add_picture",
    "add_page_break": "add_page_break",
    "add_table_of_contents": "add_toc",
    "delete_paragraph": "delete_paragraph",
    "search_and_replace": "search_replace",
    "insert_header_near_text": "insert_heading",
    "insert_line_or_paragraph_near_text": "insert_paragraph",
    "insert_numbered_list_near_text": "insert_list",
    "replace_paragraph_block_below_header": "replace_block",
    "replace_block_between_manual_anchors": "replace_anchors",
    "format_text": "format_text",
    "create_custom_style": "create_style",
    "format_table": "format_table",
    "set_table_column_width": "table_set_column_width",
    "set_table_column_widths": "table_set_column_widths",
    "set_table_width": "table_set_width",
    "set_table_cell_shading": "table_cell_shading",
    "set_table_cell_alignment": "table_cell_alignment",
    "set_table_alignment_all": "table_alignment",
    "apply_table_alternating_rows": "table_alternating",
    "highlight_table_header": "table_highlight_header",
    "merge_table_cells": "table_merge_cells",
    "merge_table_cells_horizontal": "table_merge_horizontal",
    "merge_table_cells_vertical": "table_merge_vertical",
    "auto_fit_table_columns": "table_auto_fit",
    "format_table_cell_text": "table_format_cell",
    "set_table_cell_padding": "table_cell_padding",
    "protect_document": "protect",
    "unprotect_document": "unprotect",
    "add_footnote_to_document": "add_footnote",
    "add_footnote_after_text": "add_footnote_after",
    "add_footnote_before_text": "add_footnote_before",
    "add_footnote_enhanced": "add_footnote_enhanced",
    "add_footnote_robust": "add_footnote_robust",
    "add_endnote_to_document": "add_endnote",
    "customize_footnote_style": "customize_footnote_style",
    "delete_footnote_from_document": "delete_footnote",
    "delete_footnote_robust": "delete_footnote_robust",
    "validate_document_footnotes": "validate_footnotes",
    "get_paragraph_text_from_document": "get_paragraph",
    "find_text_in_document": "find_text",
    "convert_to_pdf": "convert_to_pdf",
    "get_all_comments": "get_comments",
    "get_comments_by_author": "get_comments_author",
    "get_comments_for_paragraph": "get_comments_paragraph",
}


def _get_word_short_name(tool_name: str) -> str:
    """从 word_create_document 提取 create_document。"""
    return tool_name[len("word_"):] if tool_name.startswith("word_") else tool_name


def _parse_word_raw_output(raw: str, tool_name: str) -> dict[str, Any]:
    """解析 Word 工具的纯文本输出，返回结构化数据。"""
    short_name = _get_word_short_name(tool_name)
    action = _WORD_ACTION_MAP.get(short_name, short_name)

    result: dict[str, Any] = {
        "tool_type": "word",
        "action": action,
        "success": False,
        "message": raw[:300] if len(raw) > 300 else raw,
    }

    # 提取文件名：匹配 .docx 路径
    fn_match = _re.search(r"([^\s]+\.docx)", raw)
    if fn_match:
        result["filename"] = fn_match.group(1)

    # 判断成功/失败
    if raw.startswith("Cannot") or raw.startswith("Failed") or raw.startswith("Invalid"):
        result["success"] = False
        # 提取错误信息
        err_match = _re.search(r"(?:Cannot|Failed to)\s+[^:]+:\s*(.+)", raw)
        if err_match:
            result["error"] = err_match.group(1)
        elif "does not exist" in raw:
            result["error"] = "文档不存在"
        return result

    if "successfully" in raw or "Successfully" in raw or "added" in raw or "deleted" in raw or "Replaced" in raw or "occurrence" in raw:
        result["success"] = True

    # ── 各工具特有信息提取 ──

    # 创建文档: "Document report.docx created successfully"
    if action == "create_document":
        m = _re.search(r"'(.*?)'", raw)
        if not m:
            m = _re.search(r"Document\s+(.+?)\s+created", raw)
        if m:
            result["filename"] = m.group(1)

    # 复制文档
    elif action == "copy_document":
        m = _re.search(r"'(.*?)'", raw)
        if m:
            result["filename"] = m.group(1)

    # 合并文档
    elif action == "merge_documents":
        m = _re.search(r"(\d+)\s+documents?\s+into", raw)
        if m:
            result["count"] = int(m.group(1))

    # 添加标题: "Heading 'Intro' (level 2) added to report.docx"
    elif action == "add_heading":
        m = _re.search(r"'([^']*)'.*?level\s+(\d+)", raw)
        if m:
            result["text"] = m.group(1)
            result["level"] = int(m.group(2))

    # 添加段落
    elif action == "add_paragraph":
        result["text_preview"] = True

    # 添加表格: "Table (3x4) added to..."
    elif action == "add_table":
        m = _re.search(r"\((\d+)x(\d+)\)", raw)
        if m:
            result["rows"] = int(m.group(1))
            result["cols"] = int(m.group(2))

    # 插入图片
    elif action == "add_picture":
        m = _re.search(r"Picture\s+(.+?)\s+added", raw)
        if m:
            result["image_path"] = m.group(1)

    # 查找替换: "Replaced 3 occurrence(s) of 'foo' with 'bar'."
    elif action == "search_replace":
        m = _re.search(r"Replaced\s+(\d+)\s+occurrence", raw)
        if m:
            result["count"] = int(m.group(1))
        m = _re.search(r"of\s+'([^']*)'\s+with\s+'([^']*)'", raw)
        if m:
            result["find_text"] = m.group(1)
            result["replace_text"] = m.group(2)
        if "No occurrences" in raw:
            result["count"] = 0

    # 删除段落
    elif action == "delete_paragraph":
        m = _re.search(r"index\s+(\d+)", raw)
        if m:
            result["paragraph_index"] = int(m.group(1))

    # 保护文档
    elif action in ("protect", "unprotect"):
        if "password" in raw.lower():
            m = _re.search(r"'(.*?)'", raw)
            if m:
                result["password"] = m.group(1)

    # 脚注相关
    elif "footnote" in action or "endnote" in action:
        m = _re.search(r"(\d+)\s+(footnote|endnote)s?", raw, _re.IGNORECASE)
        if m:
            result["footnote_count"] = int(m.group(1))

    # 转换 PDF
    elif action == "convert_to_pdf":
        m = _re.search(r"'(.*?\.pdf)'", raw, _re.IGNORECASE)
        if m:
            result["output_filename"] = m.group(1)

    return result


@register_prefix("word_")
def _extract_word(
    tool_name: str, parsed: dict[str, Any], tool_input: str | None = None,
) -> dict[str, Any] | None:
    """提取 Word MCP 工具的结构化数据。

    处理两类输出：
    1. 纯文本（_raw）— 大多数工具返回成功/失败消息
    2. JSON（data）— get_document_info / get_document_outline 等
    """
    # ── 纯文本输出 ──
    if "_raw" in parsed:
        raw = parsed["_raw"]
        return _parse_word_raw_output(raw, tool_name)

    # ── JSON 输出（get_document_info, get_document_outline 等）──
    data = _get_data(parsed)
    if data is None:
        return None

    short_name = _get_word_short_name(tool_name)
    action = _WORD_ACTION_MAP.get(short_name, short_name)

    result: dict[str, Any] = {
        "tool_type": "word",
        "action": action,
        "success": True,
    }

    # get_document_info — 文档属性
    if action == "get_document_info":
        for field in ("file_name", "file_path", "file_size", "paragraph_count",
                       "character_count", "table_count", "section_count",
                       "heading_count", "page_count", "author", "title",
                       "created", "modified"):
            if field in data:
                result[field] = data[field]
        # 也检查 metadata 子对象
        metadata = data.get("metadata", data.get("properties", {}))
        if isinstance(metadata, dict):
            for field in ("author", "title", "created", "modified",
                           "last_modified_by", "revision"):
                if field not in result and field in metadata:
                    result[field] = metadata[field]

    # get_document_outline — 文档结构
    elif action == "get_document_outline":
        for field in ("file_name", "file_path", "headings", "paragraph_count",
                       "table_count", "sections"):
            if field in data:
                result[field] = data[field]
        # 扁平化 headings 数量
        headings = data.get("headings", data.get("structure", []))
        if isinstance(headings, list):
            result["heading_count"] = len(headings)

    # list_documents — 文档列表
    elif action == "list_documents":
        files = data.get("files", data.get("documents", []))
        if isinstance(files, list):
            result["files"] = files
            result["count"] = len(files)
        elif "count" in data:
            result["count"] = data["count"]

    # find_text — 搜索结果
    elif action == "find_text":
        results = data.get("results", data.get("matches", []))
        if isinstance(results, list):
            result["results"] = results
            result["count"] = len(results)

    # get_comments* — 评论
    elif action.startswith("get_comments"):
        comments = data.get("comments", data.get("results", []))
        if isinstance(comments, list):
            result["comments"] = comments
            result["count"] = len(comments)

    return result
