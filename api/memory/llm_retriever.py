"""LLM 语义检索器 — 将全量记忆注入 LLM，由 LLM 判断相关条目。

与 :mod:`api.memory.mechanical_retriever` 提供的 BM25 机械检索形成对称，
一个靠语义理解，一个靠纯机械匹配。
"""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from api.memory.manager import BaseMemoryManager
from api.providers.manager import get_manager


# ── LLM 检索提示词 ──────────────────────────────────────


FIND_RELATED_MEMORY = """
你是一位认真细心的记忆检索助手。

你的任务是：逐条阅读以下带有编号索引的AI记忆库全文，从用户的长期记忆中找出与当前查询要求相关的所有条目。

## 匹配标准

判断一条记忆是否与查询相关时，请综合以下维度：

1. **字面匹配** — 记忆描述中直接包含查询中的关键词或短语。
2. **语义关联** — 虽然用词不同，但概念上密切相关。例如"修改"与"重构"、"考试"与"复习"、"视频"与"番剧"。
3. **主题一致** — 记忆所属的分区（theme）与查询涉及的话题吻合。例如查询关于编程，优先留意"项目"分区；查询关于偏好，留意"品味"分区。
4. **时间线索** — 如果查询中出现了时间范围（如"最近""上周""7月"），优先匹配该时间段内的记忆。

## 处理规则

- 如果查询较为宽泛（如"项目""最近"），优先匹配近期记录和高引用次数的条目。
- 如果没有完全匹配的条目，可以放宽标准，选取语义上最接近的 1 到 3 条返回。
- 如果确实没有任何相关内容，返回空数组 []，不要硬凑。
- 返回的结果按相关度从高到低排序。

## 输出格式

只输出一个 JSON 数组，包含匹配条目的索引编号，按相关度降序排列：
```
[3, 7, 12]
```

## 示例

示例1：
查询要求："塔罗牌重构"
记忆库摘录：
  [0] (项目) 塔罗牌工具是Sonetto项目的人文性质彩蛋，Miso正在重构。
  [1] (瞬间) 2026年7月11日，Miso让Sonetto分析塔罗牌工具代码，识别出小阿尔卡纳粗糙、逆位缺失等重构点。
  [2] (品味) Miso 喜欢夏天和猫。
  [3] (瞬间) 2026年7月12日凌晨，Miso抽塔罗牌问期末考运势，得圣杯六（逆位）和死神（正位）。
相关条目：[0, 1, 3]
（推理：0和1直接涉及塔罗牌重构，3提到塔罗牌抽牌语义相关；2不相关）

示例2：
查询要求："期末复习范围"
记忆库摘录：
  [0] (音乐) Miso 最喜欢洛天依。
  [1] (项目) 2026年7月5日，Miso将数学复习范围整理成md复习目录。
  [2] (瞬间) 2026年7月6日，Miso考完了物理考试。
  [3] (项目) 2026年7月7日，Miso将红线划定的数学复习范围整理成md复习目录。
相关条目：[2, 1, 3]
（推理：2是考试完成，1和3是复习范围整理；0不相关）

示例3：
查询要求："喜欢看什么视频"
记忆库摘录：
  [0] (品味) Miso 喜欢看日剧《孤独的美食家》。
  [1] (项目) Miso学习前端知识，涉及TS泛型、JS箭头函数和Vue3的ref/computed。
  [2] (品味) Miso 喜欢新海诚的电影。
  [3] (项目) 塔罗牌工具正在重构中。
相关条目：[0, 2]
（推理：0和2都是视频影视偏好；1和3是项目相关，不匹配）
"""


# ── LLM 检索器 ──────────────────────────────────────────


class LLMRetriever:
    """LLM 语义检索器：将全量记忆注入 LLM，由 LLM 判断相关条目。

    与 :class:`~api.memory.mechanical_retriever.MechanicalRetriever` 对称，
    一个靠语义理解，一个靠纯机械匹配。

    用法::

        retriever = LLMRetriever(mm)
        results = retriever.retrieve("塔罗牌重构")

    Args:
        memory_manager: 已初始化的 MemoryManager 实例，用于读取全量记忆。
    """

    def __init__(self, memory_manager: BaseMemoryManager) -> None:
        self._mm = memory_manager

    def retrieve(self, prompt: str) -> list[dict[str, str]]:
        """根据查询提示检索相关记忆条目，返回 ``{id, description, theme}`` 列表。

        Args:
            prompt: 用户查询文本。

        Returns:
            相关记忆条目列表，按相关度降序排列。
            若无相关记忆或 LLM 不可用，返回空列表。
        """
        mgr = get_manager()
        if mgr is None or mgr.get_default_llm() is None:
            return []
        llm = mgr.get_default_llm()
        items = self._mm.show()
        if not items:
            return []

        # 格式化为带列表序号的编号列表，供 LLM 引用
        lines = []
        for i, item in enumerate(items):
            lines.append(f"[{i}] ({item['theme']}) {item['description']}")
        memory_text = "\n".join(lines)
        user_prompt = f"## 记忆库\n{memory_text}\n\n## 查询要求\n{prompt}"

        response = llm.invoke(
            [SystemMessage(content=FIND_RELATED_MEMORY.strip()), HumanMessage(content=user_prompt)],
            config=RunnableConfig(callbacks=[]),
        )

        try:
            indices = json.loads(response.content)
            if isinstance(indices, list):
                return [
                    {"id": items[i]["id"], "description": items[i]["description"], "theme": items[i]["theme"]}
                    for i in indices if 0 <= i < len(items)
                ]
        except (json.JSONDecodeError, TypeError, IndexError):
            pass
        return []

    async def aretrieve(self, prompt: str) -> list[dict[str, str]]:
        """异步检索相关记忆条目（支持 asyncio 取消）。

        与 :meth:`retrieve` 逻辑相同，但使用 ``ainvoke`` 替代 ``invoke``，
        可被 ``asyncio.Task.cancel()`` 中断。用于 RetrieveMemoryNode 的
        竞速模式（检索 vs 用户跳过）。
        """
        mgr = get_manager()
        if mgr is None or mgr.get_default_llm() is None:
            return []
        llm = mgr.get_default_llm()
        items = self._mm.show()
        if not items:
            return []

        lines = []
        for i, item in enumerate(items):
            lines.append(f"[{i}] ({item['theme']}) {item['description']}")
        memory_text = "\n".join(lines)
        user_prompt = f"## 记忆库\n{memory_text}\n\n## 查询要求\n{prompt}"

        response = await llm.ainvoke(
            [SystemMessage(content=FIND_RELATED_MEMORY.strip()), HumanMessage(content=user_prompt)],
            config=RunnableConfig(callbacks=[]),
        )

        try:
            indices = json.loads(response.content)
            if isinstance(indices, list):
                return [
                    {"id": items[i]["id"], "description": items[i]["description"], "theme": items[i]["theme"]}
                    for i in indices if 0 <= i < len(items)
                ]
        except (json.JSONDecodeError, TypeError, IndexError):
            pass
        return []
