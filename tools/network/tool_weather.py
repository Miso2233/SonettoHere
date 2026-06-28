"""Tool: get_current_weather — 天气查询。"""

from datetime import datetime
from statistics import mean
from typing import Any

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success


class WeatherInput(BaseModel):
    get_doc: bool = Field(
        default=False, description="设为 true 以获取使用说明和领域知识"
    )
    city: str = Field(default="", description="城市名称，如'北京'、'Shanghai'")
    adcode: str = Field(default="", description="行政区划代码，如'110000'")
    extended: bool = Field(
        default=False, description="返回体感温度/能见度/气压/紫外线/AQI等扩展信息"
    )
    forecast: bool = Field(default=False, description="返回最多7天预报")
    hourly: bool = Field(default=False, description="返回24小时逐小时预报")
    minutely: bool = Field(default=False, description="返回分钟级降水预报（仅国内）")
    indices: bool = Field(default=False, description="返回18项生活指数")
    lang: str = Field(default="zh", description="语言：zh/en")


# ── 降水强度分级（基于 2 分钟窗口 max_precip，经验阈值） ──
_INTENSITY_LEVELS: list[tuple[float, str]] = [
    (5.0, "暴雨"),
    (2.0, "大雨"),
    (0.5, "中雨"),
    (0.1, "小雨"),
]


def _classify_intensity(max_precip: float) -> str:
    for threshold, label in _INTENSITY_LEVELS:
        if max_precip >= threshold:
            return label
    return "微量"


def _strip_tz(ts: str) -> str:
    if ts.endswith("+08:00"):
        return ts[:-6]
    return ts


def _build_range(points: list[dict[str, Any]]) -> dict[str, Any]:
    """从连续降水点列表构建一个区间统计。"""
    precip_values = [p.get("precip", 0) for p in points]
    max_precip = max(precip_values)
    avg_precip = mean(precip_values)

    start = points[0].get("time", "")
    end = points[-1].get("time", "")

    # 估算持续分钟数
    duration = len(points) * 2  # 回退：每点 2 分钟
    if start and end:
        try:
            fmt = "%Y-%m-%dT%H:%M:%S"
            s = datetime.strptime(_strip_tz(start), fmt)
            e = datetime.strptime(_strip_tz(end), fmt)
            diff = (e - s).total_seconds()
            if diff > 0:
                duration = max(1, round(diff / 60))
        except (ValueError, IndexError):
            pass

    return {
        "start": start,
        "end": end,
        "max_precip": round(max_precip, 2),
        "avg_precip": round(avg_precip, 2),
        "intensity": _classify_intensity(max_precip),
        "duration_minutes": duration,
    }


def _summarize_minutely(data: dict[str, Any]) -> dict[str, Any]:
    """
    将分钟级降水 ~120 个原始数据点压缩为连续降水区间。

    读取 data 中 ``minutely_precip`` / ``minutely`` / ``minutely_forecast`` 任一键，
    返回压缩后的结构：

    .. code-block:: python

        {
            "summary": "未来两小时有间歇性降雨",
            "update_time": "2026-06-28T17:34:03+08:00",
            "range_count": 2,
            "original_point_count": 120,
            "ranges": [ { "start": ..., "end": ..., "max_precip": 2.5,
                          "avg_precip": 1.3, "intensity": "中雨",
                          "duration_minutes": 18 }, ... ],
        }
    """
    raw = data.get("minutely_precip") or data.get("minutely") or data.get("minutely_forecast")
    if not raw:
        return {"summary": "无分钟级降水数据", "ranges": [], "range_count": 0}

    summary = raw.get("summary", "")
    update_time = raw.get("update_time", "")
    records = raw.get("data", [])

    if not records:
        return {
            "summary": summary,
            "update_time": update_time,
            "ranges": [],
            "range_count": 0,
            "original_point_count": 0,
        }

    # 合并连续降水区间
    ranges: list[dict[str, Any]] = []
    current: list[dict[str, Any]] | None = None

    for r in records:
        precip = r.get("precip", 0)
        if precip > 0:
            if current is None:
                current = [r]
            else:
                current.append(r)
        else:
            if current is not None:
                ranges.append(_build_range(current))
                current = None

    if current is not None:
        ranges.append(_build_range(current))

    return {
        "summary": summary,
        "update_time": update_time,
        "ranges": ranges,
        "range_count": len(ranges),
        "original_point_count": len(records),
    }


class WeatherTool(ToolBase):
    name: str = "get_current_weather"
    description: str = (
        "获取指定城市的天气信息。支持实时天气、多天预报、逐小时预报、分钟级降水、生活指数。"
        "city 和 adcode 二选一即可。[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = WeatherInput

    def _run(
        self,
        get_doc: bool = False,
        city: str = "",
        adcode: str = "",
        extended: bool = False,
        forecast: bool = False,
        hourly: bool = False,
        minutely: bool = False,
        indices: bool = False,
        lang: str = "zh",
    ) -> str:
        if get_doc:
            return self._load_doc()

        try:
            result = self.client.uapi.misc.get_misc_weather(
                city=city,
                adcode=adcode,
                extended=extended,
                forecast=forecast,
                hourly=hourly,
                minutely=minutely,
                indices=indices,
                lang=lang,
            )
            # 自动压缩分钟级降水数据，替换原始 ~120 点数组，避免 LLM 接触冗余信息
            if minutely:
                compressed = _summarize_minutely(result)
                # 替换所有原始键，确保 LLM 只看压缩版
                for key in ("minutely_precip", "minutely", "minutely_forecast"):
                    if key in result:
                        result[key] = compressed
            return format_success(result)
        except Exception as e:
            return format_error(f"天气查询失败: {e}")
