"""Tool: holiday_calendar — 节假日与万年历查询。"""

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success


class HolidayCalendarInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明和领域知识")
    date: str = Field(default="", description="按天查询，格式 YYYY-MM-DD（与 month/year 三选一）")
    month: str = Field(default="", description="按月查询，格式 YYYY-MM（与 date/year 三选一）")
    year: str = Field(default="", description="按年查询，格式 YYYY（与 date/month 三选一）")
    timezone: str = Field(default="Asia/Shanghai", description="时区")
    holiday_type: str = Field(
        default="all",
        description="节日类型: all/legal/legal_rest/legal_workday/solar/lunar/term",
    )
    include_nearby: bool = Field(default=False, description="是否返回前后最近节日（仅 date 模式）")
    nearby_limit: int = Field(default=7, ge=1, le=30, description="最近节日数量限制")


class HolidayCalendarTool(ToolBase):
    name: str = "holiday_calendar"
    description: str = (
        "查询指定日期/月份/年份的万年历与节假日信息。"
        "支持农历、节气、法定节假日。[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = HolidayCalendarInput

    def _run(
        self,
        get_doc: bool = False,
        date: str = "",
        month: str = "",
        year: str = "",
        timezone: str = "Asia/Shanghai",
        holiday_type: str = "all",
        include_nearby: bool = False,
        nearby_limit: int = 7,
    ) -> str:
        if get_doc:
            return self._load_doc()
        if not date and not month and not year:
            return format_error("必须提供 date、month 或 year 参数之一")

        try:
            result = self.client.uapi.misc.get_misc_holiday_calendar(
                date=date,
                month=month,
                year=year,
                timezone=timezone,
                holiday_type=holiday_type,
                include_nearby=include_nearby,
                nearby_limit=nearby_limit,
                exclude_past=True,
            )
            return format_success(result)
        except Exception as e:
            return format_error(f"节假日查询失败: {e}")
