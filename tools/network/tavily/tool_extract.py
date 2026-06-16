"""Tavily Extract — 从 URL 提取网页内容（Markdown），替代 WebScraperSkill。"""

from typing import Any

from pydantic import BaseModel, Field
from tavily import TavilyClient

from tools.base import ToolBase, format_success, format_error


class TavilyExtractInput(BaseModel):
    """tavily_extract 输入参数"""

    urls: list[str] = Field(
        description="目标 URL 列表（最多 20 个）",
    )
    extract_depth: str = Field(
        default="basic",
        description="提取深度: basic / advanced（JS 渲染页用 advanced）",
    )
    query: str | None = Field(
        default=None,
        description="定向提取关键词，仅返回相关片段",
    )
    chunks_per_source: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description="每源返回片段数（需配合 query）",
    )


class TavilyExtractTool(ToolBase):
    """从 URL 列表提取网页内容（Markdown 格式），支持一次性批量提取和定向提取。"""

    name: str = "tavily_extract"
    description: str = (
        "从指定 URL 提取网页内容，返回 Markdown 格式的正文。"
        "支持一次最多 20 个 URL，支持定向提取（query 参数筛选相关片段）。"
        "JS 渲染页面请使用 advanced 深度。"
        "Agent 应先用 tavily_search 发现相关链接，再用此工具深入阅读内容。"
        "[调用积极性: 可自由看情况调用] [get_doc: 无 get_doc 选项]"
    )
    args_schema: type[BaseModel] = TavilyExtractInput

    _tavily: TavilyClient | None = None

    @property
    def _tavily_client(self) -> TavilyClient:
        if self._tavily is None:
            from config.settings import get_settings

            key = get_settings().tavily_api_key
            if not key:
                raise ValueError("TAVILY_API_KEY 未配置，请在 .env 中设置")
            self._tavily = TavilyClient(api_key=key)
        return self._tavily

    def _run(self, **kwargs: Any) -> str:
        try:
            urls = kwargs.get("urls", [])
            if not urls:
                return format_error("URL 列表不能为空")

            extract_depth = kwargs.get("extract_depth", "basic")
            query = kwargs.get("query")
            chunks_per_source = kwargs.get("chunks_per_source")

            # 构建参数
            params: dict[str, Any] = {
                "urls": urls,
                "extract_depth": extract_depth,
            }
            if query is not None:
                params["query"] = query
            if chunks_per_source is not None:
                params["chunks_per_source"] = chunks_per_source

            result = self._tavily_client.extract(**params)

            # Tavily extract 返回格式:
            # { results: [{ url, title, raw_content, images }], failed_results, response_time }
            return format_success({
                "results": result.get("results", []),
                "failed_results": result.get("failed_results", []),
                "response_time": result.get("response_time", 0),
            })

        except Exception as e:
            return format_error(f"Tavily 提取失败: {e!s}")
