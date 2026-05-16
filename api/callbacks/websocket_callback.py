"""WebSocket 回调 — 将 LangChain 事件转为结构化 JSON 推送到前端。"""

import ast
import json
import time
from typing import Any

from fastapi import WebSocket
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


def _extract_content(output: Any) -> str:
    """从工具输出中提取字符串内容。

    LangChain ToolMessage 的 __str__ 会返回 "content='...' name='...' tool_call_id='...'"
    这种无法解析的格式，需要取其 .content 属性获取真正的 JSON。
    """
    if hasattr(output, 'content'):
        return str(output.content)
    if not isinstance(output, str):
        return str(output)
    return output


def _fmt_temp(val: Any) -> str:
    """将温度值格式化为 "14°C" 字符串。"""
    if isinstance(val, (int, float)):
        return f"{val}°C"
    return str(val) if val else ""


class WebSocketCallback(BaseCallbackHandler):
    def __init__(self, ws: WebSocket):
        super().__init__()
        self._ws = ws
        self._thinking_started = False
        self._tool_start_time: dict[str, float] = {}
        self._tool_names: dict[str, str] = {}
        self._tool_inputs: dict[str, str] = {}

    @staticmethod
    def _extract_tool_data(tool_name: str, output: Any, tool_input: str | None = None) -> dict[str, Any] | None:
        """从工具输出中提取前端专属气泡所需的结构化数据。"""
        out_str = _extract_content(output)
        try:
            parsed = json.loads(out_str)
        except (json.JSONDecodeError, TypeError):
            return None

        if tool_name == "bilibili_download":
            data = parsed.get("data", {})
            if not isinstance(data, dict):
                return None
            cover_path = data.get("cover_path", "")
            return {
                "video_title": data.get("title"),
                "cover_url": f"/api/file?path={cover_path}" if cover_path else None,
                "file_path": data.get("file_path"),
                "quality": data.get("quality"),
            }

        # ── Todo 系列工具 ──
        if tool_name.startswith("todo_"):
            data = parsed.get("data", {})
            if not isinstance(data, dict):
                return None

            if tool_name == "todo_list":
                tool_type = "task_list"
            elif tool_name == "todo_list_projects":
                tool_type = "project_list"
            else:
                tool_type = "single_task"

            result: dict[str, Any] = {"tool_type": tool_type}
            if tool_type == "task_list":
                result["total"] = data.get("total")
                tasks = data.get("tasks", [])
                if isinstance(tasks, list):
                    result["tasks"] = tasks
            elif tool_type == "project_list":
                result["total"] = data.get("total")
                projects = data.get("projects", [])
                if isinstance(projects, list):
                    result["projects"] = projects
            else:
                for field in ("task_id", "content", "due_date", "priority",
                              "project", "message", "is_completed"):
                    if field in data:
                        result[field] = data[field]
            return result

        # ── Task Tracker ──
        if tool_name == "task_tracker":
            data = parsed.get("data", {})
            if not isinstance(data, dict):
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

        # ── Python 执行 ──
        if tool_name == "run_python":
            data = parsed.get("data", {})
            if not isinstance(data, dict):
                return None
            result: dict[str, Any] = {
                "tool_type": "run_python",
                "stdout": data.get("output", ""),
            }
            # 从输入端提取代码（LangChain 传入的是 Python repr 格式，非 JSON）
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

        # ── 文件操作 ──
        if tool_name == "file_operations":
            data = parsed.get("data", {})
            if not isinstance(data, dict):
                return None

            # 从输入端获取操作类型（LangChain 传入的是 Python repr 格式）
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

        # ── 塔罗占卜 ──
        if tool_name == "tarot":
            data = parsed.get("data", {})
            if not isinstance(data, dict):
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

        # ── 答案之书 ──
        if tool_name == "answer_book":
            data = parsed.get("data", {})
            if not isinstance(data, dict):
                return None
            return {
                "tool_type": "answer_book",
                "question": data.get("question", ""),
                "answer": data.get("answer", ""),
            }

        # ── 地图系列 ──
        if tool_name in ("nearby_search", "fuzzy_address_search"):
            data = parsed.get("data", {})
            if not isinstance(data, dict):
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

        if tool_name == "geocode_address":
            data = parsed.get("data", {})
            if not isinstance(data, dict):
                return None
            return {
                "address": data.get("address", ""),
                "location": data.get("location", ""),
            }

        if tool_name == "get_transit_route":
            data = parsed.get("data", {})
            if not isinstance(data, dict):
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

        if tool_name == "get_cycling_route":
            data = parsed.get("data", {})
            if not isinstance(data, dict):
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

        # ── 天气查询 ──
        if tool_name == "get_current_weather":
            data = parsed.get("data", {})
            if not isinstance(data, dict):
                return None
            temp_val = data.get("temperature")
            if isinstance(temp_val, (int, float)):
                temp_str = f"{temp_val}°C"
            else:
                temp_str = str(temp_val) if temp_val else ""
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
                result["temp_feel"] = f"{feels}°C" if isinstance(feels, (int, float)) else str(feels)
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

        # ── 时间查询 ──
        if tool_name == "time_skill":
            data = parsed.get("data", {})
            if not isinstance(data, dict):
                return None
            return {
                "tool_type": "time",
                "datetime": data.get("datetime", ""),
                "date": data.get("date", ""),
                "time": data.get("time", ""),
                "weekday": data.get("weekday", ""),
                "timezone": data.get("timezone", ""),
            }

        # ── 语法检查 ──
        if tool_name == "syntax_checker":
            data = parsed.get("data", {})
            if not isinstance(data, dict):
                return None
            return {
                "tool_type": "syntax_check",
                "language": data.get("language", ""),
                "errors": data.get("errors", []),
                "warnings": data.get("warnings", []),
            }

        # ── B站 Cookie 设置 ──
        if tool_name == "bilibili_set_cookie":
            data = parsed.get("data", {})
            if not isinstance(data, dict):
                return None
            return {
                "tool_type": "set_cookie",
                "message": data.get("message", ""),
            }

        # ── 图片理解 ──
        if tool_name == "analyze_image":
            data = parsed.get("data", {})
            if not isinstance(data, dict):
                return None
            return {
                "tool_type": "analyze_image",
                "response": data.get("response", ""),
            }

        # ── 节假日查询 ──
        if tool_name == "holiday_calendar":
            data = parsed.get("data", {})
            if not isinstance(data, dict):
                return None
            result: dict[str, Any] = {"mode": data.get("mode", "")}

            # 查询参数
            query = data.get("query")
            if isinstance(query, dict):
                for field in ("date", "month", "year"):
                    if query.get(field):
                        result[field] = query[field]

            # 统计摘要
            summary = data.get("summary")
            if isinstance(summary, dict):
                for field in ("total_days", "holiday_events", "rest_days", "legal_rest_days", "workdays"):
                    if field in summary:
                        result[field] = summary[field]

            # 日期明细（取第一天用于展示农历、星期等）
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
                # 向上兼容：取第一条的农历和星期
                first = result["days"][0] if result["days"] else None
                if first:
                    result.setdefault("weekday", first["weekday"])
                    if first["lunar_date"]:
                        result["lunar_date"] = first["lunar_date"]
                    if first["solar_term"]:
                        result["solar_term"] = first["solar_term"]

            # 节日事件
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

            # 附近节日（dict: {previous, next}）
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

        return None

    async def on_llm_start(
        self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any
    ) -> None:
        self._thinking_started = True
        await self._ws.send_json({
            "type": "thinking_start",
            "payload": {"timestamp": time.time()},
        })

    async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        await self._ws.send_json({
            "type": "token",
            "payload": {"token": token},
        })

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        if self._thinking_started:
            self._thinking_started = False
            await self._ws.send_json({
                "type": "thinking_end",
                "payload": {"timestamp": time.time()},
            })

    async def on_tool_start(
        self, serialized: dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        tool_name = serialized.get("name", "unknown")
        run_id = str(kwargs.get("run_id", ""))
        self._tool_start_time[run_id] = time.time()
        self._tool_names[run_id] = tool_name
        self._tool_inputs[run_id] = input_str

        await self._ws.send_json({
            "type": "tool_start",
            "payload": {
                "tool_name": tool_name,
                "input": input_str[:500] if len(input_str) > 500 else input_str,
            },
        })

    async def on_tool_end(self, output: str, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", ""))
        elapsed = time.time() - self._tool_start_time.pop(run_id, time.time())
        tool_name = self._tool_names.pop(run_id, "unknown")
        tool_input = self._tool_inputs.pop(run_id, None)

        out_str = _extract_content(output)

        # 提取工具专属结构化数据
        tool_data = self._extract_tool_data(tool_name, output, tool_input)

        if len(out_str) > 300:
            out_str = out_str[:300] + f"... (共 {len(out_str)} 字符)"

        await self._ws.send_json({
            "type": "tool_end",
            "payload": {
                "tool_name": tool_name,
                "output": out_str,
                "elapsed": round(elapsed, 2),
                "tool_data": tool_data,
            },
        })

    async def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", ""))
        self._tool_start_time.pop(run_id, None)
        self._tool_inputs.pop(run_id, None)
        tool_name = self._tool_names.pop(run_id, "unknown")
        await self._ws.send_json({
            "type": "tool_error",
            "payload": {
                "tool_name": tool_name,
                "error": str(error),
            },
        })
