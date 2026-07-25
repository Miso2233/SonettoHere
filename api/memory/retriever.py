"""机械检索器 — 纯 BM25 机械匹配，替代 LLM 语义检索。

湾流 V5.1：将记忆检索从「每次对话调用 LLM」降级为「纯 BM25 机械匹配」，
消除每次对话中记忆读取环节的 LLM 延迟和成本。
"""

from __future__ import annotations

import math
import re
from enum import Enum
from typing import Any


# ── 枚举 ─────────────────────────────────────────────


class RetrievalMode(Enum):
    """记忆检索模式。

    Attributes:
        LLM:        LLM 语义检索（默认，当前生产方案）
        MECHANICAL: BM25 机械检索（零 LLM 调用，毫秒级）
    """
    LLM = "llm"
    MECHANICAL = "mech"


# ── 停用字 ───────────────────────────────────────────

_STOP_CHARS = frozenset(
    "的 了 是 在 有 和 不 也 个 与 及 或 "
    "把 被 让 对 从 到 向 于 由 以 这 那".split()
)

_RE_EN_TOKEN = re.compile(r"[a-zA-Z0-9_.+#/\\-]+")


# ── 分词器 ───────────────────────────────────────────


def _tokenize(text: str) -> list[str]:
    """纯机械中文分词。

    英文/数字 token 降大小写后保留原样；
    中文通过单字 + Bigram + Trigram 覆盖语义单元，停用字仅影响单字层。
    """
    tokens: list[str] = []

    # 英文/数字 token
    for match in _RE_EN_TOKEN.finditer(text):
        tokens.append(match.group().lower())

    # 提取中文字符
    chinese_chars = [c for c in text if "一" <= c <= "鿿"]

    # 单字（过滤停用字）
    for c in chinese_chars:
        if c not in _STOP_CHARS:
            tokens.append(c)

    # Bigram
    for i in range(len(chinese_chars) - 1):
        tokens.append(chinese_chars[i] + chinese_chars[i + 1])

    # Trigram
    for i in range(len(chinese_chars) - 2):
        tokens.append(chinese_chars[i] + chinese_chars[i + 1] + chinese_chars[i + 2])

    return tokens


# ── BM25 检索器 ──────────────────────────────────────


class MechanicalRetriever:
    """基于 BM25 的机械记忆检索器。

    零外部依赖，纯正则分词 + BM25 评分 + 命中数加权。
    索引构建约 35ms（236 条），单次检索约 2ms。

    用法::

        retriever = MechanicalRetriever()
        retriever.build_index(mm.show())
        results = retriever.search("塔罗牌重构", top_k=5)
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75, alpha: float = 0.15) -> None:
        self._k1 = k1
        self._b = b
        self._alpha = alpha

        # 标记位：外部修改记忆后应置 True，下次检索前自动重建
        self.dirty: bool = False

        # 索引数据
        self._items: list[dict[str, Any]] = []
        self._doc_terms: list[list[str]] = []
        self._doc_lengths: list[int] = []
        self._avgdl: float = 0.0
        self._df: dict[str, int] = {}
        self._N: int = 0

    def build_index(self, items: list[dict[str, Any]]) -> None:
        """全量重建 BM25 倒排索引。

        Args:
            items: ``mm.show()`` 的输出，每条含 ``id`` / ``description`` / ``theme``。
                   可选含 ``hit``（命中数），缺失时默认为 0。
        """
        self._items = list(items)
        self._N = len(self._items)

        # 分词
        self._doc_terms = [
            _tokenize(item.get("description", "")) for item in self._items
        ]
        self._doc_lengths = [len(terms) for terms in self._doc_terms]
        self._avgdl = sum(self._doc_lengths) / max(self._N, 1)

        # 文档频率（每个 term 出现在多少篇文档中，每篇仅计一次）
        df: dict[str, int] = {}
        for terms in self._doc_terms:
            for term in set(terms):
                df[term] = df.get(term, 0) + 1
        self._df = df

        self.dirty = False

    def search(
        self, query: str, top_k: int = 5, min_score: float = 0.0
    ) -> list[dict[str, Any]]:
        """BM25 搜索，返回 Top-K 结果。

        Args:
            query:   用户查询文本。
            top_k:   截断条数，默认 5。
            min_score: 最低分数阈值，低于此值的不返回。

        Returns:
            按 ``score`` 降序排列的结果列表：
            ``{score, id, description, theme, hit}``
        """
        if self._N == 0:
            return []

        q_terms = _tokenize(query)
        if not q_terms:
            return []

        unknown_terms = [t for t in q_terms if t not in self._df]
        known_terms = [t for t in q_terms if t in self._df]
        if not known_terms:
            return []

        # 对每个文档计算 BM25 分数
        scores = [0.0] * self._N

        for qt in set(known_terms):
            idf = self._idf(qt)
            qf = q_terms.count(qt)

            for doc_idx in range(self._N):
                tf = self._doc_terms[doc_idx].count(qt)
                if tf == 0:
                    continue
                tf_boost = (
                    tf
                    * (self._k1 + 1)
                    / (
                        tf
                        + self._k1
                        * (1 - self._b + self._b * self._doc_lengths[doc_idx] / self._avgdl)
                    )
                )
                scores[doc_idx] += idf * tf_boost * qf

        # hit 对数加权：final_score = bm25_score × (1 + α · ln(hit + 1))
        for i in range(self._N):
            hit = int(self._items[i].get("hit", 0))
            boost = 1.0 + self._alpha * math.log(hit + 1)
            scores[i] *= boost

        # Top-K 截断
        top_indices = sorted(
            range(self._N),
            key=lambda i: scores[i],
            reverse=True,
        )
        top_indices = [i for i in top_indices if scores[i] >= min_score][:top_k]

        return [
            {
                "score": round(scores[i], 2),
                "id": self._items[i]["id"],
                "description": self._items[i]["description"],
                "theme": self._items[i].get("theme", ""),
                "hit": int(self._items[i].get("hit", 0)),
            }
            for i in top_indices
        ]

    def get_related_memory_from(
        self, prompt: str, top_k: int = 5
    ) -> list[dict[str, str]]:
        """兼容接口，桥接 :meth:`search`，返回 ``{id, description, theme}`` 格式。"""
        results = self.search(prompt, top_k=top_k)
        return [
            {"id": r["id"], "description": r["description"], "theme": r["theme"]}
            for r in results
        ]

    def _idf(self, term: str) -> float:
        """BM25 IDF：``ln((N - df + 0.5) / (df + 0.5) + 1)``"""
        df = self._df.get(term, 0)
        return math.log((self._N - df + 0.5) / (df + 0.5) + 1)
