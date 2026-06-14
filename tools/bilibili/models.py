"""Bilibili 视频下载 — 数据模型。"""

from pydantic import BaseModel

# 画质 ID → 名称
QUALITY_MAP = {
    127: "超高清 8K",
    126: "杜比视界 4K",
    120: "超清 4K",
    116: "高清 1080P60",
    112: "高清 1080P+",
    80: "高清 1080P",
    74: "高清 720P60",
    64: "高清 720P",
    32: "清晰 480P",
    16: "流畅 360P",
}

# 别名 → quality_id（"highest" 为 None，表示选最高）
QUALITY_ALIAS = {
    "8K": 127,
    "4K": 120,
    "1080P60": 116,
    "1080P": 80,
    "720P60": 74,
    "720P": 64,
    "480P": 32,
    "360P": 16,
    "highest": None,
}


class VideoInfo(BaseModel):
    """从 B 站页面解析出的视频元信息。"""
    url: str
    title: str = ""
    quality_id: int = 0
    video_url: str = ""
    audio_url: str = ""
    is_durl: bool = False
    part_number: int = 1
    output_path: str = ""
    cover_path: str = ""

    def get_quality_name(self) -> str:
        return QUALITY_MAP.get(self.quality_id, f"未知 (ID={self.quality_id})")
