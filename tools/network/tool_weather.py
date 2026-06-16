"""Tool: get_current_weather — 天气查询。"""

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success


class WeatherInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明和领域知识")
    city: str = Field(default="", description="城市名称，如'北京'、'Shanghai'")
    adcode: str = Field(default="", description="行政区划代码，如'110000'")
    extended: bool = Field(default=False, description="返回体感温度/能见度/气压/紫外线/AQI等扩展信息")
    forecast: bool = Field(default=False, description="返回最多7天预报")
    hourly: bool = Field(default=False, description="返回24小时逐小时预报")
    minutely: bool = Field(default=False, description="返回分钟级降水预报（仅国内）")
    indices: bool = Field(default=False, description="返回18项生活指数")
    lang: str = Field(default="zh", description="语言：zh/en")


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
            return format_success(result)
        except Exception as e:
            return format_error(f"天气查询失败: {e}")
