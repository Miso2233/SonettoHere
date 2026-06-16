"""Tool: geocode_address — 地址转经纬度坐标。"""

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success


class GeocodeInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明和领域知识")
    address: str = Field(default="", description="详细地址字符串，如'北京市海淀区中关村大街'")


class GeocodeTool(ToolBase):
    name: str = "geocode_address"
    description: str = (
        "将详细地址转换为经纬度坐标（GCJ-02 火星坐标系）。"
        "返回坐标可直接用于 nearby_search / get_transit_route / get_cycling_route。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = GeocodeInput

    def _run(self, get_doc: bool = False, address: str = "") -> str:
        if get_doc:
            return self._load_doc()
        if not address:
            return format_error("address 不能为空")

        try:
            data = self.client.amap_request(
                "/v3/geocode/geo",
                {"address": address, "output": "json"},
            )

            if data.get("status") == "1" and data.get("geocodes"):
                location = data["geocodes"][0]["location"]
                return format_success({"address": address, "location": location})
            return format_error(f"地理编码失败，未找到'{address}'的坐标")
        except Exception as e:
            return format_error(f"地理编码异常: {e}")
