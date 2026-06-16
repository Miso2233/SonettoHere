"""Tavily Search — LLM 优化的网络搜索工具，替代 SmartSearchSkill。"""

from typing import Any

from pydantic import BaseModel, Field
from tavily import TavilyClient

from tools.base import ToolBase, format_success, format_error


class TavilySearchInput(BaseModel):
    """tavily_search 输入参数"""

    query: str = Field(description="搜索关键词（400 字符以内）")
    max_results: int = Field(default=5, ge=1, le=20, description="返回结果数")
    search_depth: str = Field(
        default="basic",
        description="搜索深度: ultra-fast / fast / basic / advanced",
    )
    time_range: str | None = Field(
        default=None,
        description="时间范围: day / week / month / year",
    )
    include_domains: list[str] | None = Field(
        default=None,
        description="限定搜索的域名列表",
    )
    exclude_domains: list[str] | None = Field(
        default=None,
        description="排除的域名列表",
    )
    include_answer: bool = Field(
        default=False,
        description="是否包含 AI 摘要回答",
    )
    include_raw_content: bool = Field(
        default=False,
        description="是否包含全文内容",
    )


class TavilySearchTool(ToolBase):
    """使用 Tavily Search API 执行网络搜索，支持深度/时间/域名等多维度控制。"""

    name: str = "tavily_search"
    description: str = (
        "使用 Tavily 执行网络搜索，返回结构化结果（标题、URL、摘要、相关度分数）。"
        "支持多级搜索深度（ultra-fast/fast/basic/advanced）、时间范围筛选、"
        "域名白名单/黑名单、AI 摘要回答、全文内容提取。"
        "Agent 应先用此工具搜索发现相关链接，再用 tavily_extract 深入阅读内容。"
        "[调用积极性: 可自由看情况调用] [get_doc: 无 get_doc 选项]"
    )
    args_schema: type[BaseModel] = TavilySearchInput

    # 注意: client 字段被 ToolBase 占用（SharedAPIClient），这里用 _tavily 代替
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
            query = kwargs.get("query", "")
            max_results = kwargs.get("max_results", 5)
            search_depth = kwargs.get("search_depth", "basic")
            time_range = kwargs.get("time_range")
            include_domains = kwargs.get("include_domains")
            exclude_domains = kwargs.get("exclude_domains")
            include_answer = kwargs.get("include_answer", False)
            include_raw_content = kwargs.get("include_raw_content", False)

            # 构建 Tavily 请求参数（仅传非 None 参数）
            params: dict[str, Any] = {
                "query": query,
                "max_results": max_results,
                "search_depth": search_depth,
                "include_answer": include_answer,
                "include_raw_content": include_raw_content,
            }
            if time_range is not None:
                params["time_range"] = time_range
            if include_domains is not None:
                params["include_domains"] = include_domains
            if exclude_domains is not None:
                params["exclude_domains"] = exclude_domains

            result = self._tavily_client.search(**params)

            # Tavily 返回格式: { query, answer, results: [...], response_time }
            return format_success({
                "query": result.get("query", query),
                "answer": result.get("answer", ""),
                "results": result.get("results", []),
                "response_time": result.get("response_time", 0),
            })

        except Exception as e:
            return format_error(f"Tavily 搜索失败: {e!s}")
