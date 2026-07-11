"""Tool: tarot — 塔罗牌占卜（韦特塔罗 RWS）。"""

import random
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success

# 从 YAML 数据文件加载 78 张韦特塔罗牌（22 大阿尔卡纳 + 56 小阿尔卡纳）
_DECK_PATH = Path(__file__).resolve().parent / "tarot_deck.yaml"
with open(_DECK_PATH, encoding="utf-8") as _f:
    TAROT_DECK: list[dict] = yaml.safe_load(_f)["cards"]

SPREADS = {
    "single": {"name": "单牌占卜", "positions": 1, "descriptions": ["当前问题"]},
    "three": {
        "name": "三牌占卜",
        "positions": 3,
        "descriptions": ["过去", "现在", "未来"],
    },
    "celtic": {
        "name": "凯尔特十字",
        "positions": 10,
        "descriptions": [
            "当前状况",
            "挑战/阻碍",
            "最佳路径/建议",
            "潜在基础",
            "过去",
            "近期未来",
            "自我形象",
            "外在因素/他人影响",
            "希望/恐惧",
            "最终结果",
        ],
    },
}


class TarotInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")
    question: str = Field(default="", description="占卜问题")
    spread_type: str = Field(default="three", description="牌阵: single/three/celtic")


class TarotTool(ToolBase):
    name: str = "tarot"
    description: str = (
        "韦特塔罗牌占卜（RWS）。支持单牌/三牌/凯尔特十字三种牌阵。仅供娱乐参考。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = TarotInput

    def _run(
        self,
        get_doc: bool = False,
        question: str = "",
        spread_type: str = "three",
    ) -> str:
        if get_doc:
            return self._load_doc()
        if not question:
            return format_error("占卜问题不能为空")
        if spread_type not in SPREADS:
            return format_error(
                f"不支持的牌阵: {spread_type}，可选: single/three/celtic"
            )

        spread = SPREADS[spread_type]
        deck = TAROT_DECK.copy()
        random.shuffle(deck)

        cards = []
        for i in range(spread["positions"]):
            card = deck[i].copy()
            card["is_reversed"] = random.random() < 0.15
            pos = (
                spread["descriptions"][i]
                if i < len(spread["descriptions"])
                else f"位置{i + 1}"
            )
            meanings = card["reversed"] if card["is_reversed"] else card["upright"]
            status = "逆位" if card["is_reversed"] else "正位"

            cards.append(
                {
                    "card_id": card["id"],
                    "name": card["name"],
                    "name_en": card["name_en"],
                    "symbol": card.get("symbol", ""),
                    "suit": card.get("suit", "大阿尔卡纳"),
                    "element": card.get("element", ""),
                    "keywords": card["keywords"],
                    "fortune": random.choice(meanings),
                    "position": pos,
                    "status": status,
                    "orientation": "reversed" if card["is_reversed"] else "upright",
                    "meaning": meanings,
                    "description": f"{card['name']}（{status}）— {', '.join(meanings[:3])}",
                }
            )

        return format_success(
            {
                "question": question,
                "spread_type": spread_type,
                "spread_name": spread["name"],
                "cards_count": spread["positions"],
                "cards": cards,
            }
        )
