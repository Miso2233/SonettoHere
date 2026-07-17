"""Tool: read_image — 多模态 LLM 主动获取本地图片信息。

读取本地图片文件，通过 Command 机制将图片数据以 HumanMessage 形式
注入 graph 状态，使 LLM 在当前轮次直接看到图片内容。
"""

import base64
import mimetypes
from pathlib import Path

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import InjectedToolCallId
from langgraph.types import Command
from pydantic import BaseModel, Field
from typing_extensions import Annotated

from tools.base import ToolBase, check_path_access, format_error, format_success


class ReadImageInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")
    image_path: str = Field(
        default="",
        description="本地图片的绝对路径，如 C:\\Users\\...\\photo.jpg",
    )
    tool_call_id: Annotated[str, InjectedToolCallId] = ""


class ReadImageTool(ToolBase):
    name: str = "read_image"
    description: str = (
        "读取本地图片文件，将图片内容注入 LLM 上下文，"
        "使你可以直接看到并分析该图片。"
        "当用户提到本地图片文件时调用此工具，而非 analyze_image "
        "（后者使用外部模型分析，适用于 URL 图片）。"
        "仅接受本地文件路径，不支持 URL。"
        "[调用积极性: 当用户明确提供图片路径或描述某张本地图片时，优先调用此工具]"
    )
    args_schema: type[BaseModel] = ReadImageInput

    def _run(
        self,
        get_doc: bool = False,
        image_path: str = "",
        tool_call_id: str = "",
    ) -> Command:
        if get_doc:
            # get_doc 模式返回加载文档说明
            return Command(update={
                "messages": [
                    ToolMessage(content=self._load_doc(), tool_call_id=tool_call_id),
                ],
            })

        if not image_path:
            return Command(update={
                "messages": [
                    ToolMessage(
                        content=format_error("image_path 不能为空"),
                        tool_call_id=tool_call_id,
                        status="error",
                    ),
                ],
            })

        # 安全校验
        err = check_path_access(image_path)
        if err:
            return Command(update={
                "messages": [
                    ToolMessage(
                        content=format_error(err),
                        tool_call_id=tool_call_id,
                        status="error",
                    ),
                ],
            })

        # 文件存在性检查
        path = Path(image_path)
        if not path.exists():
            return Command(update={
                "messages": [
                    ToolMessage(
                        content=format_error(f"文件不存在: {image_path}"),
                        tool_call_id=tool_call_id,
                        status="error",
                    ),
                ],
            })
        if not path.is_file():
            return Command(update={
                "messages": [
                    ToolMessage(
                        content=format_error(f"路径不是文件: {image_path}"),
                        tool_call_id=tool_call_id,
                        status="error",
                    ),
                ],
            })

        # 读取图片字节
        try:
            image_bytes = path.read_bytes()
        except PermissionError:
            return Command(update={
                "messages": [
                    ToolMessage(
                        content=format_error(f"无权限读取文件: {image_path}"),
                        tool_call_id=tool_call_id,
                        status="error",
                    ),
                ],
            })
        except OSError as e:
            return Command(update={
                "messages": [
                    ToolMessage(
                        content=format_error(f"读取文件失败: {e}"),
                        tool_call_id=tool_call_id,
                        status="error",
                    ),
                ],
            })

        # 推断 MIME 类型并验证是否为图片
        mime, _ = mimetypes.guess_type(image_path)
        if mime is None:
            mime = "image/png"
        elif not mime.startswith("image/"):
            return Command(update={
                "messages": [
                    ToolMessage(
                        content=format_error(f"文件类型 {mime} 不是图片，仅支持图片文件"),
                        tool_call_id=tool_call_id,
                        status="error",
                    ),
                ],
            })

        # 构造含 base64 图片数据的多模态 HumanMessage
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime};base64,{image_b64}"

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=format_success({
                            "file_name": path.name,
                            "file_size": len(image_bytes),
                            "mime_type": mime,
                        }),
                        tool_call_id=tool_call_id,
                    ),
                    HumanMessage(content=[
                        {
                            "type": "text",
                            "text": f"LLM 主动读取了本地图片（{path.name}）：",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url},
                        },
                    ]),
                ],
            },
            goto="model",
        )
