"""Tool: fuzzy_address_search — 模糊地址/POI 搜索。"""

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success
from tools.map.map_api import parse_poi_response


class FuzzyAddressInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明和领域知识")
    keywords: str = Field(default="", description="搜索关键字，如'北京大学'、'肯德基'")
    city: str | None = Field(default=None, description="限定城市，如'北京'")
    types: str | None = Field(default=None, description="POI类型码，如'050000'（餐饮）")
    citylimit: bool = Field(default=False, description="是否严格限定城市范围")
    offset: int = Field(default=20, description="每页记录数")
    page: int = Field(default=1, description="当前页数")


class FuzzyAddressTool(ToolBase):
    name: str = "fuzzy_address_search"
    description: str = (
        "通过关键字模糊搜索地点/POI。返回名称、地址、坐标等信息。"
        "建议指定 city 提高准确率。[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = FuzzyAddressInput

    def _run(
        self,
        get_doc: bool = False,
        keywords: str = "",
        city: str | None = None,
        types: str | None = None,
        citylimit: bool = False,
        offset: int = 20,
        page: int = 1,
    ) -> str:
        if get_doc:
            return self._load_doc()
        if not keywords:
            return format_error("keywords 不能为空")

        try:
            params: dict = {
                "keywords": keywords,
                "output": "json",
                "offset": offset,
                "page": page,
                "extensions": "base",
            }
            if city:
                params["city"] = city
            if types:
                params["types"] = types
            if citylimit:
                params["citylimit"] = "true"

            data = self.client.amap_request("/v3/place/text", params)
            result = parse_poi_response(data)

            if result["status"] == "1":
                return format_success({
                    "keywords": keywords,
                    "city": city,
                    "count": result["count"],
                    "pois": result["pois"],
                })
            return format_error(f"模糊搜索失败: {result.get('info', '未知错误')}")
        except Exception as e:
            return format_error(f"模糊搜索异常: {e}")
