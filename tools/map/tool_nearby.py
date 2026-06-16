"""Tool: nearby_search — 附近地点搜索。"""

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success
from tools.map.map_api import parse_poi_response


class NearbySearchInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明和领域知识")
    location: str = Field(default="", description='中心点坐标，格式为"经度,纬度"')
    keywords: str | None = Field(default=None, description="搜索关键字，如'肯德基'")
    types: str | None = Field(default=None, description="POI类型码，如'050000'（餐饮）")
    radius: int = Field(default=1000, description="搜索半径（米），0-50000")
    sortrule: int = Field(default=1, description="0=距离排序，1=综合排序")
    offset: int = Field(default=20, description="每页记录数")
    page: int = Field(default=1, description="当前页数")


class NearbySearchTool(ToolBase):
    name: str = "nearby_search"
    description: str = (
        "在指定坐标附近搜索兴趣点（POI）。支持关键字/类型筛选和半径设置。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = NearbySearchInput

    def _run(
        self,
        get_doc: bool = False,
        location: str = "",
        keywords: str | None = None,
        types: str | None = None,
        radius: int = 1000,
        sortrule: int = 1,
        offset: int = 20,
        page: int = 1,
    ) -> str:
        if get_doc:
            return self._load_doc()
        if not location:
            return format_error("location 不能为空")
        if not keywords and not types:
            return format_error("keywords 和 types 至少必选其一")

        try:
            params: dict = {
                "location": location,
                "output": "json",
                "offset": offset,
                "page": page,
                "extensions": "base",
                "sortrule": sortrule,
                "radius": radius,
            }
            if keywords:
                params["keywords"] = keywords
            if types:
                params["types"] = types

            data = self.client.amap_request("/v3/place/around", params)
            result = parse_poi_response(data)

            if result["status"] == "1":
                return format_success({
                    "location": location,
                    "keywords": keywords,
                    "radius": radius,
                    "count": result["count"],
                    "pois": result["pois"],
                })
            return format_error(f"附近搜索失败: {result.get('info', '未知错误')}")
        except Exception as e:
            return format_error(f"附近搜索异常: {e}")
