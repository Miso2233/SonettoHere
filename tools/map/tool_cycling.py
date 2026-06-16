"""Tool: get_cycling_route — 骑行路线规划。"""

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success
from tools.map.map_api import parse_cycling_response


class CyclingRouteInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明和领域知识")
    origin_longitude: str = Field(default="", description="起点经度")
    origin_latitude: str = Field(default="", description="起点纬度")
    destination_longitude: str = Field(default="", description="终点经度")
    destination_latitude: str = Field(default="", description="终点纬度")


class CyclingRouteTool(ToolBase):
    name: str = "get_cycling_route"
    description: str = (
        "查询骑行路线规划。返回距离、耗时、逐段导航指令和道路名称。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = CyclingRouteInput

    def _run(
        self,
        get_doc: bool = False,
        origin_longitude: str = "",
        origin_latitude: str = "",
        destination_longitude: str = "",
        destination_latitude: str = "",
    ) -> str:
        if get_doc:
            return self._load_doc()
        if not all([origin_longitude, origin_latitude, destination_longitude, destination_latitude]):
            return format_error("起点和终点经纬度不能为空")

        try:
            data = self.client.amap_request(
                "/v4/direction/bicycling",
                {
                    "origin": f"{origin_longitude},{origin_latitude}",
                    "destination": f"{destination_longitude},{destination_latitude}",
                },
            )

            result = parse_cycling_response(data)

            if result.get("paths"):
                return format_success({
                    "origin": f"{origin_longitude},{origin_latitude}",
                    "destination": f"{destination_longitude},{destination_latitude}",
                    "path_count": len(result["paths"]),
                    "paths": result["paths"],
                })
            return format_error(f"未找到合适的骑行路线: {result.get('message', '')}")
        except Exception as e:
            return format_error(f"骑行路线查询异常: {e}")
