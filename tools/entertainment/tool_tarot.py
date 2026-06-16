"""Tool: tarot — 塔罗牌占卜（韦特塔罗 RWS）。"""

import random

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success

# 78 张韦特塔罗牌（22 大阿尔卡纳 + 56 小阿尔卡纳）
TAROT_DECK: list[dict] = [
    {"id": 0, "name": "愚人", "name_en": "The Fool", "symbol": "0", "element": "风", "keywords": ["自由", "天真", "冒险", "无限可能"], "upright": ["新的开始", "自发行动", "不虑后果", "自由奔跑", "纯真乐观"], "reversed": ["轻率", "愚蠢", "冲动", "不计后果", "缺乏方向"]},
    {"id": 1, "name": "魔术师", "name_en": "The Magician", "symbol": "I", "element": "风", "keywords": ["意志力", "创造力", "技能", "沟通"], "upright": ["创造奇迹", "敏锐", "变通", "足智多谋", "技能纯熟"], "reversed": ["欺骗", "技巧不足", "策划无力", "意志薄弱", "潜能不能发挥"]},
    {"id": 2, "name": "女祭司", "name_en": "The High Priestess", "symbol": "II", "element": "水", "keywords": ["直觉", "神秘", "智慧", "内在声音"], "upright": ["直觉", "洞察", "内在智慧", "神秘学", "沉静观察"], "reversed": ["秘密", "隐瞒", "内在恐惧", "直觉迟钝", "隐秘信息"]},
    {"id": 3, "name": "女皇", "name_en": "The Empress", "symbol": "III", "element": "地", "keywords": ["丰盛", "母性", "创造力", "自然"], "upright": ["丰收", "繁荣", "创造力", "温暖", "舒适"], "reversed": ["依赖", "墨守成规", "空洞", "创作障碍", "不成熟"]},
    {"id": 4, "name": "皇帝", "name_en": "The Emperor", "symbol": "IV", "element": "火", "keywords": ["权威", "结构", "控制", "父亲形象"], "upright": ["领导", "成就", "理性", "秩序", "影响力"], "reversed": ["暴政", "僵硬", "缺乏自律", "逃避责任", "幼稚"]},
    {"id": 5, "name": "教皇", "name_en": "The Hierophant", "symbol": "V", "element": "土", "keywords": ["信仰", "道德", "传统", "精神指导"], "upright": ["精神寄托", "宗教信仰", "传统价值", "道德标准", "慈善"], "reversed": ["叛逆", "新奇", "个人寻找", "打破传统", "精神空虚"]},
    {"id": 6, "name": "恋人", "name_en": "The Lovers", "symbol": "VI", "element": "风", "keywords": ["爱情", "选择", "结合", "伙伴关系"], "upright": ["爱情", "美好", "结合", "选择", "价值观一致"], "reversed": ["不和", "错误选择", "犹豫", "价值观冲突", "沟通不良"]},
    {"id": 7, "name": "战车", "name_en": "The Chariot", "symbol": "VII", "element": "水", "keywords": ["意志力", "胜利", "控制", "自律"], "upright": ["胜利", "克服障碍", "意志坚定", "自律", "成功"], "reversed": ["失败", "失控", "方向迷失", "疲劳", "冲突"]},
    {"id": 8, "name": "力量", "name_en": "Strength", "symbol": "VIII", "element": "火", "keywords": ["勇气", "耐心", "慈悲", "内在力量"], "upright": ["勇气", "意志坚定", "慈悲", "内在力量", "坚韧不拔"], "reversed": ["恐惧", "内心脆弱", "自我怀疑", "失控", "耐心不足"]},
    {"id": 9, "name": "隐士", "name_en": "The Hermit", "symbol": "IX", "element": "水", "keywords": ["内省", "孤独", "寻求真理", "独处"], "upright": ["内省", "独处", "寻找真相", "沉静", "指引"], "reversed": ["孤立", "孤独感", "自闭", "拒绝帮助", "黑暗内省"]},
    {"id": 10, "name": "命运之轮", "name_en": "Wheel of Fortune", "symbol": "X", "element": "火", "keywords": ["命运", "转变", "循环", "运气"], "upright": ["命运转变", "机缘巧合", "生命循环", "幸运", "关键转折"], "reversed": ["厄运", "运气不佳", "停滞", "命运逆转", "错失良机"]},
    {"id": 11, "name": "正义", "name_en": "Justice", "symbol": "XI", "element": "风", "keywords": ["公正", "真相", "法律", "因果"], "upright": ["公正", "诚实", "法律", "因果报应", "真相"], "reversed": ["不公", "偏见", "谎言", "法律纠纷", "报应"]},
    {"id": 12, "name": "倒吊人", "name_en": "The Hanged Man", "symbol": "XII", "element": "水", "keywords": ["暂停", "牺牲", "换位思考", "等待"], "upright": ["暂停", "牺牲", "换位思考", "等待时机", "以退为进"], "reversed": ["拖延", "牺牲无果", "拒绝改变", "无谓牺牲", "被动等待"]},
    {"id": 13, "name": "死神", "name_en": "Death", "symbol": "XIII", "element": "水", "keywords": ["结束", "转变", "蜕变", "释放"], "upright": ["结束", "转变", "蜕变", "释放", "放下过去"], "reversed": ["抗拒改变", "停滞", "僵化", "恐惧结束", "原地踏步"]},
    {"id": 14, "name": "节制", "name_en": "Temperance", "symbol": "XIV", "element": "火", "keywords": ["平衡", "调和", "耐心", "中庸之道"], "upright": ["平衡", "调和", "耐心", "中庸之道", "净化"], "reversed": ["失衡", "极端", "缺乏耐心", "浪费", "污染"]},
    {"id": 15, "name": "恶魔", "name_en": "The Devil", "symbol": "XV", "element": "土", "keywords": ["束缚", "欲望", "物质主义", "沉溺"], "upright": ["束缚", "欲望", "物质主义", "沉溺", "沉迷"], "reversed": ["解脱", "打破束缚", "克服成瘾", "释放", "重获自由"]},
    {"id": 16, "name": "塔", "name_en": "The Tower", "symbol": "XVI", "element": "火", "keywords": ["突变", "毁灭", "觉醒", "解放"], "upright": ["突变", "毁灭", "警醒", "脱离困境", "意外转变"], "reversed": ["保守", "抗拒改变", "拖延", "内部动荡", "延误"]},
    {"id": 17, "name": "星星", "name_en": "The Star", "symbol": "XVII", "element": "水", "keywords": ["希望", "灵感", "宁静", "信心"], "upright": ["希望", "灵感", "宁静", "信心", "恢复"], "reversed": ["绝望", "灵感枯竭", "失去信心", "灰心", "迷茫"]},
    {"id": 18, "name": "月亮", "name_en": "The Moon", "symbol": "XVIII", "element": "水", "keywords": ["幻觉", "恐惧", "直觉", "潜意识"], "upright": ["幻觉", "恐惧", "直觉", "潜意识", "不安"], "reversed": ["恐惧消散", "拨云见日", "看清真相", "解除焦虑", "走出迷茫"]},
    {"id": 19, "name": "太阳", "name_en": "The Sun", "symbol": "XIX", "element": "火", "keywords": ["快乐", "成功", "活力", "温暖"], "upright": ["快乐", "成功", "活力", "温暖", "生命力"], "reversed": ["悲伤", "失败", "倦怠", "冷淡", "失去活力"]},
    {"id": 20, "name": "审判", "name_en": "Judgement", "symbol": "XX", "element": "火", "keywords": ["复活", "觉醒", "审判", "更新"], "upright": ["复活", "觉醒", "审判", "更新", "重新开始"], "reversed": ["自我怀疑", "犹豫", "忽视内心召唤", "评判他人", "后悔"]},
    {"id": 21, "name": "世界", "name_en": "The World", "symbol": "XXI", "element": "土", "keywords": ["完成", "成就", "整合", "圆满"], "upright": ["完成", "成就", "整合", "圆满", "成功"], "reversed": ["未完成", "停滞", "缺乏成就感", "半途而废", "目标未达成"]},
]

# 56 张小阿尔卡纳（简化：仅保留名称和关键词，完整含义随牌阵附上）
_SUITS = {
    "权杖": ["Ace", "二", "三", "四", "五", "六", "七", "八", "九", "十", "侍者", "骑士", "皇后", "国王"],
    "圣杯": ["Ace", "二", "三", "四", "五", "六", "七", "八", "九", "十", "侍者", "骑士", "皇后", "国王"],
    "宝剑": ["Ace", "二", "三", "四", "五", "六", "七", "八", "九", "十", "侍者", "骑士", "皇后", "国王"],
    "星币": ["Ace", "二", "三", "四", "五", "六", "七", "八", "九", "十", "侍者", "骑士", "皇后", "国王"],
}
_MINOR_ELEMENTS = {"权杖": "火", "圣杯": "水", "宝剑": "风", "星币": "土"}

for suit, ranks in _SUITS.items():
    for rank in ranks:
        TAROT_DECK.append({
            "id": len(TAROT_DECK),
            "name": f"{suit}{rank}",
            "name_en": f"{rank} of {suit}",
            "symbol": rank[0] if rank in ("Ace",) else rank,
            "suit": suit,
            "element": _MINOR_ELEMENTS[suit],
            "keywords": [suit, rank],
            "upright": [f"{suit}能量顺畅", "积极发展", "正面特质"],
            "reversed": [f"{suit}能量受阻", "延迟发展", "需关注内在"],
        })

SPREADS = {
    "single": {"name": "单牌占卜", "positions": 1, "descriptions": ["当前问题"]},
    "three": {"name": "三牌占卜", "positions": 3, "descriptions": ["过去", "现在", "未来"]},
    "celtic": {
        "name": "凯尔特十字",
        "positions": 10,
        "descriptions": [
            "当前状况", "挑战/阻碍", "最佳路径/建议", "潜在基础", "过去",
            "近期未来", "自我形象", "外在因素/他人影响", "希望/恐惧", "最终结果",
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
            return format_error(f"不支持的牌阵: {spread_type}，可选: single/three/celtic")

        spread = SPREADS[spread_type]
        deck = TAROT_DECK.copy()
        random.shuffle(deck)

        cards = []
        for i in range(spread["positions"]):
            card = deck[i].copy()
            card["is_reversed"] = random.random() < 0.15
            pos = spread["descriptions"][i] if i < len(spread["descriptions"]) else f"位置{i + 1}"
            meanings = card["reversed"] if card["is_reversed"] else card["upright"]
            status = "逆位" if card["is_reversed"] else "正位"

            cards.append({
                "card_id": card["id"],
                "name": card["name"],
                "name_en": card["name_en"],
                "symbol": card.get("symbol", ""),
                "suit": card.get("suit", "大阿尔卡纳"),
                "element": card.get("element", ""),
                "keywords": card["keywords"],
                "position": pos,
                "status": status,
                "orientation": "reversed" if card["is_reversed"] else "upright",
                "meaning": meanings,
                "description": f"{card['name']}（{status}）— {', '.join(meanings[:3])}",
            })

        return format_success({
            "question": question,
            "spread_type": spread_type,
            "spread_name": spread["name"],
            "cards_count": spread["positions"],
            "cards": cards,
        })
