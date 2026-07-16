# 数据资源层 — `api/data/`

## 层级定位

**第⑦层（最底层）**，与 `core/`（核心基础设施层）同属架构最底层。

数据资源层是 SonettoHere 后端分层架构中的**最底层**，不依赖任何其他模块，仅被上层模块读取或写入。

```
┌──────────────────────────────────────┐
│          上层模块 (routes/            │
│         providers/ session/)          │  ← 依赖 data/
├──────────────────────────────────────┤
│  ⑦ 数据资源层 (data/)                 │  纯静态资源、文件存储
└──────────────────────────────────────┘
```

## 模块内容

| 文件 / 目录 | 类型 | 用途 | 管理方式 |
|---|---|---|---|
| `news.yaml` | YAML 文件 | 系统更新动态数据 | 手动编辑（版本管理） |
| `SonettoTest.png` | PNG 图片 | 视觉能力检测测试资源 | 静态文件（Git 管理） |
| `const-sessions/` | 目录 | 固定会话持久化存储 | 运行时由 `const_store` 读写 |

### 目录结构

```
api/data/
├── news.yaml              # 系统更新动态
├── SonettoTest.png        # 视觉检测测试图片
└── const-sessions/        # 固定会话 YAML 持久化目录（运行时创建）
```

## 职责描述

### 1. 静态数据提供

`news.yaml` 存储系统更新动态，供 REST API `/api/news` 端点读取。数据格式为 YAML 列表，每条记录包含标题、描述、类型、日期、标签等信息。

### 2. 测试资源

`SonettoTest.png` 是一张包含文字 "Sonetto" 的测试图片，用于模型视觉能力检测。在保存 LLM 提供商配置时，系统向每个模型发送此图片并检测其是否能正确识别图片中的文字。

### 3. 固定会话文件存储目录

`const-sessions/` 目录为运行时目录，由 `api/session/const_store.py` 管理。当用户将会话标记为「固定会话」时，会话状态（元数据 + 对话消息）会序列化为 YAML 文件持久化到此目录中。应用启动时，系统会从该目录加载所有固定会话并重建到内存 SessionManager 中。

## 设计要点

| 要点 | 说明 |
|---|---|
| **纯静态资源** | 模块本身不含任何运行时 Python 逻辑，仅提供文件存储 |
| **无运行时逻辑** | 所有读写操作由上层模块（routes、providers、session）完成 |
| **无外部依赖** | 不导入任何项目内模块，也不依赖数据库等外部服务 |
| **文件即接口** | 模块边界通过文件路径约定，而非函数调用 |

## 被依赖关系

| 上层模块 | 文件路径 | 用途 | 操作类型 |
|---|---|---|---|
| `api/routes/news.py` | `api/data/news.yaml` | 读取系统更新动态并返回 REST API 响应 | 只读 |
| `api/providers/vision.py` | `api/data/SonettoTest.png` | 加载测试图片并发送给模型进行视觉能力检测 | 只读 |
| `api/session/const_store.py` | `api/data/const-sessions/` | 固定会话的 YAML 持久化读写 | 读写 |
| `api/server.py` | `api/data/const-sessions/` | 应用启动时加载所有固定会话到内存 | 只读 |

## 关键代码片段

### 读取 news.yaml（`api/routes/news.py`）

```python
from fastapi import APIRouter
from pydantic import BaseModel
from pathlib import Path
import yaml

router = APIRouter()

NEWS_PATH = Path(__file__).resolve().parent.parent / "data" / "news.yaml"


class NewsEntry(BaseModel):
    id: str
    en_title: str | None = None
    title: str
    description: str
    type: str
    date: str
    tags: list[str] = []
    version: str
    pr_number: int | None = None


class ListNewsResponse(BaseModel):
    news: list[NewsEntry]


def _load_news() -> list[NewsEntry]:
    if not NEWS_PATH.exists():
        return []
    with open(NEWS_PATH, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    entries = [NewsEntry(**item) for item in raw.get("news", [])]
    # 按日期降序排列（最新的在前）
    entries.sort(key=lambda e: e.date, reverse=True)
    return entries


@router.get("/news", response_model=ListNewsResponse)
def list_news():
    """返回所有更新动态，按日期降序排列。"""
    return ListNewsResponse(news=_load_news())
```

### 引用 SonettoTest.png（`api/providers/vision.py`）

```python
IMAGE_PATH = Path(__file__).resolve().parent.parent / "data" / "SonettoTest.png"
```

### const-sessions 目录操作（`api/session/const_store.py`）

```python
_CONST_DIR = Path(__file__).resolve().parent.parent / "data" / "const-sessions"

def _ensure_dir() -> Path:
    _CONST_DIR.mkdir(parents=True, exist_ok=True)
    return _CONST_DIR

def load_all_const_sessions() -> list[dict]:
    """扫描 const-sessions/ 目录，加载所有 YAML。"""
    ensure_dir = _ensure_dir()
    sessions = []
    for fpath in sorted(ensure_dir.glob("*.yaml")):
        data = load_const_session(fpath)
        if data and data.get("session_id"):
            sessions.append(data)
    return sessions
```

## 演进建议

### 数据量增长时的迁移考量

当前 `data/` 模块采用纯文件存储方式，在小规模场景下简单可靠。若未来数据量增长，以下场景建议考虑迁移到数据库：

| 场景 | 当前方式的问题 | 建议迁移方案 | 优先级 |
|---|---|---|---|
| 更新动态条目超过数百条 | YAML 文件过大，加载效率下降 | 迁移到 SQLite 或 PostgreSQL | 低 |
| 固定会话数量激增 | YAML 文件散落目录，查询效率低 | 迁移到关系型数据库 + 索引 | 中 |
| 需要按条件过滤或搜索 | 需全量加载后内存过滤 | 数据库查询（WHERE / LIKE 等） | 低 |
| 多实例部署 | 文件存储无法共享 | 对象存储（S3/MinIO）或 PostgreSQL | 高 |

### 保持现状的场景

如果项目保持单实例部署且数据量可控，当前的文件存储方案完全足够，无需引入数据库带来的运维复杂度。
