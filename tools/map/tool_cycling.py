"""Tool: get_cycling_route — 骑行路线规划。"""

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success, off_thread
from tools.get_doc import get_doc
from tools.map.map_api import parse_cycling_response


class CyclingRouteInput(BaseModel):
    origin_longitude: str = Field(default="", description="起点经度")
    origin_latitude: str = Field(default="", description="起点纬度")
    destination_longitude: str = Field(default="", description="终点经度")
    destination_latitude: str = Field(default="", description="终点纬度")


@get_doc
class CyclingRouteTool(ToolBase):
    name: str = "get_cycling_route"
    description: str = (
        "查询骑行路线规划。返回距离、耗时、逐段导航指令和道路名称。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = CyclingRouteInput

    async def _arun(
        self,
        origin_longitude: str = "",
        origin_latitude: str = "",
        destination_longitude: str = "",
        destination_latitude: str = "",
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
                "/v4/direction/bicycling",
                {
                    "origin": f"{origin_longitude},{origin_latitude}",
                    "destination": f"{destination_longitude},{destination_latitude}",
                },
            )

            result = parse_cycling_response(data)

            if result.get("paths"):
                return format_success(
                    {
                        "origin": f"{origin_longitude},{origin_latitude}",
                        "destination": f"{destination_longitude},{destination_latitude}",
                        "path_count": len(result["paths"]),
                        "paths": result["paths"],
                    }
                )
            return format_error(f"未找到合适的骑行路线: {result.get('message', '')}")
        except Exception as e:
            return format_error(f"骑行路线查询异常: {e}")
