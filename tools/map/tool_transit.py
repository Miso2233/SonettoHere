"""Tool: get_transit_route — 公共交通路线规划。"""

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success, off_thread
from tools.get_doc import get_doc
from tools.map.map_api import parse_transit_response


class TransitRouteInput(BaseModel):
    origin_longitude: str = Field(default="", description="起点经度")
    origin_latitude: str = Field(default="", description="起点纬度")
    destination_longitude: str = Field(default="", description="终点经度")
    destination_latitude: str = Field(default="", description="终点纬度")
    origin_city: str = Field(default="北京", description="起点城市名称")
    destination_city: str = Field(default="北京", description="终点城市名称")


@get_doc
class TransitRouteTool(ToolBase):
    name: str = "get_transit_route"
    description: str = (
        "查询公交/地铁公共交通路线规划。返回多方案，含费用、耗时、步行距离、换乘详情。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = TransitRouteInput

    def _run(self, **kwargs: object) -> str:
        raise NotImplementedError("get_transit_route 仅支持异步模式，请使用 _arun")

    async def _arun(
        self,
        origin_longitude: str = "",
        origin_latitude: str = "",
        destination_longitude: str = "",
        destination_latitude: str = "",
        origin_city: str = "北京",
        destination_city: str = "北京",
    ) -> str:
        if not all(
            [
                origin_longitude,
                origin_latitude,
                destination_longitude,
                destination_latitude,
            ]
        ):
            return format_error("起点和终点经纬度不能为空")

        try:
            data = await off_thread(
                self.client.amap_request,
                "/v3/direction/transit/integrated",
                {
                    "origin": f"{origin_longitude},{origin_latitude}",
                    "destination": f"{destination_longitude},{destination_latitude}",
                    "city": origin_city,
                    "cityd": destination_city,
                    "strategy": "0",
                    "nightflag": "0",
                },
            )

            result = parse_transit_response(data)

            if result.get("routes"):
                return format_success(
                    {
                        "origin": f"{origin_longitude},{origin_latitude}",
                        "destination": f"{destination_longitude},{destination_latitude}",
                        "origin_city": origin_city,
                        "destination_city": destination_city,
                        "route_count": len(result["routes"]),
                        "routes": result["routes"],
                    }
                )
            return format_error("未找到合适的公交路线")
        except Exception as e:
            return format_error(f"公交路线查询异常: {e}")
