"""Tool: verify_image — 本地图片校验与处理。

接收本地图片路径，校验文件存在且为有效图片，将图片数据以多模态
HumanMessage 形式注入 checkpoint（供下一轮 Agent 读取），返回确认结果。
"""

import base64

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from api.agent import interaction
from tools.base import ToolBase, format_success
from tools.network.tool_image_understand import load_image_bytes


class VerifyImageInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")
    image_path: str = Field(
        default="",
        description="本地图片的绝对路径，如 C:\\Users\\...\\photo.jpg",
    )


class VerifyImageTool(ToolBase):
    name: str = "verify_image"
    description: str = (
        "校验本地图片文件是否存在、是否为有效图片格式，并返回确认结果。"
        "支持常见图片格式（jpg、png、gif、bmp、webp）。"
        "仅接受本地文件路径，不支持 URL。[调用积极性: 仅在用户明确提供图片路径或要求处理图片时调用]"
    )
    args_schema: type[BaseModel] = VerifyImageInput

    def _run(self, get_doc: bool = False, image_path: str = "") -> str:
        if get_doc:
            return self._load_doc()
        if not image_path:
            return format_success({"status": "跳过", "reason": "未提供图片路径"})

        # 加载图片（内部含安全校验 + 文件存在性检查）
        image_bytes, mime = load_image_bytes(f"local:{image_path}")

        # 构造多模态 HumanMessage（含 base64 图片数据）注入 checkpoint
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime};base64,{image_b64}"
        hm = HumanMessage(content=[
            {"type": "text", "text": "用户验证了以下本地图片："},
            {"type": "image_url", "image_url": {"url": data_url}},
        ])

        session_id = interaction.current_session_id.get()
        if session_id:
            interaction.queue_human_message(session_id, hm)

        return format_success({"status": "成功", "message": "成功（而不是图片信息）"})
