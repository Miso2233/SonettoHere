# Project Jet 喷气计划 — 网络基础设施替换为 Tavily

## 一、项目概述

**Project Jet**（喷气计划）的目标是：将 SonettoHere 现有的网络搜索和网页抓取工具全面替换为 **Tavily Search API**，利用其 LLM 优化的搜索结果、内容提取、深度研究等能力，淘汰基于 UAPI 的 `smart_search` 和基于 Playwright 的 `scrape_webpage`，同时新增爬取、站点发现、研究报告等能力。

"喷气"寓意旧引擎（活塞式）换新引擎（喷气式）—— 更快、更稳、覆盖更广。

### 1.1 现状 vs 目标

| 维度 | 现状 | Jet 目标 |
|------|------|---------|
| 搜索工具 | `smart_search`（UAPI，仅返回摘要） | `tavily_search`（全文、时间范围、域过滤、AI 摘要） |
| 抓取工具 | `scrape_webpage`（Playwright 浏览器，重） | `tavily_extract`（API 直呼，轻量） |
| 深度研究 | ❌ 无 | `tavily_research`（多源综合，带引用） |
| 站点爬取 | ❌ 无 | `tavily_crawl`（整站批量提取） |
| 站点发现 | ❌ 无 | `tavily_map`（URL 发现） |
| 上下文效率 | 搜索结果含导航/广告噪声 | 动态搜索模式筛选后仅 `print()` 信号进入上下文 |

### 1.2 核心原则

1. **功能对等** — 新工具必须覆盖旧工具的常用场景，不降级用户体验
2. **额外价值** — 替换不是简单平移，Tavily 的能力优势要体现在新工具的参数和输出上
3. **渐进替换** — 新工具就绪后旧工具再从注册表移除，不出现空窗期
4. **前端适配** — 前端气泡组件为新工具重新设计（黑白简约风），删除旧组件
5. **上下文友好** — 继承 dynamic-search skill 的理念，搜索结果经滤波后再进入上下文中

---

## 二、现有工具分析

### 2.1 `smart_search` — 搜索工具

**文件：** `skills/network/skill_search.py`
**前端气泡：** `SearchBubble.vue`
**提取器：** `_extract_smart_search`（`tool_extractors.py`）

**参数：**
| 参数 | 类型 | 说明 |
|------|------|------|
| `query` | str | 搜索关键词 |
| `site` | str | 限定网站域名 |
| `filetype` | str | 限定文件类型 |
| `get_doc` | bool | 读取使用说明 |

**返回值：** `{ results: [{ title, url, snippet, domain, source, position, score, publish_time }], sources, process_time_ms }`

**局限：**
- 只返回摘要片段，无全文内容
- 无法按时间范围筛选
- 无法按相关度深度控制
- 后端依赖 UAPI 聚合服务，灵活性受限

### 2.2 `scrape_webpage` — 网页抓取工具

**文件：** `skills/network/skill_scraper.py`
**前端气泡：** `ScraperBubble.vue`
**提取器：** `_extract_scrape`（`tool_extractors.py`）

**参数：**
| 参数 | 类型 | 说明 |
|------|------|------|
| `url` | str | 目标 URL |
| `wait_ms` | int | 等待毫秒（默认 5000） |
| `screenshot` | bool | 是否截图 |
| `headless` | bool | 是否无头模式 |
| `get_doc` | bool | 读取使用说明 |

**返回值：** `{ url, title, meta, open_graph, twitter_card, structured_data, headings, links, images, content(HTML), screenshot_base64 }`

**局限：**
- 需要 Playwright 浏览器实例，资源开销大
- 提取深度受限于浏览器渲染速度
- 截图和完整元数据提取对 LLM 场景多数时候冗余
- 需要额外的 `browser_manager.py` 管理浏览器生命周期

### 2.3 架构中需涉及的修改点

| 层次 | 文件 | 修改类型 |
|------|------|---------|
| 后端工具定义 | `skills/network/`（新建 `tavily/` 子包） | 新增 |
| 工具注册 | `skills/__init__.py` | 新增 + 删除 |
| 数据提取器 | `api/callbacks/tool_extractors.py` | 新增 + 删除 |
| 前端气泡 | `web/src/components/tools/`（新建 2 个） | 新增 + 删除 |
| 前端注册表 | `web/src/components/tools/registry.ts` | 新增 + 删除 |
| API Key 配置 | `config/settings.py` / `.env` | 新增 |

---

## 三、Tavily API 能力覆盖对照

### 3.1 功能矩阵

| Tavily 能力 | 对应旧工具 | 能力提升 |
|-------------|-----------|---------|
| `search()` | `smart_search` | ✅ 多深度（basic/advanced/fast/ultra-fast）、时间范围（day/week/month/year）、域过滤（include/exclude）、全文内容（raw_content）、AI 摘要（answer） |
| `extract()` | `scrape_webpage` | ✅ 无需浏览器、Markdown 输出、一次 20 URL、query 定向提取、JS 渲染页面 advanced 模式 |
| `research()` | ❌ 无对应 | 🆕 多源综合分析报告，带引用标注 |
| `crawl()` | ❌ 无对应 | 🆕 整站批量提取，支持路径选择 |
| `map()` | ❌ 无对应 | 🆕 站点 URL 发现 |

### 3.2 Tavily 不及旧工具之处（缺口）

| 场景 | 旧工具有 | Tavily 无 | 是否需要弥补 |
|------|---------|-----------|------------|
| 页面截图 | `scrape_webpage(screenshot=true)` | 无 | ❌ 非 LLM 核心场景，可舍弃 |
| Open Graph / Twitter Card 提取 | `scrape_webpage` 返回完整 OG 元数据 | `extract()` 不返回结构化 OG | ❌ Markdown 正文通常已包含所需信息 |
| JSON-LD 结构化数据 | `scrape_webpage` 提取 | `extract()` 不返回 | ❌ Agent 场景极少需要原始 JSON-LD |
| 网站域名限定 | `smart_search(site=...)` | ✅ 但需通过 `include_domains` 参数 | ✅ `search()` 的 `include_domains` 等效 |
| 文件类型限定 | `smart_search(filetype=...)` | 无 | ⚠️ 低频场景，缺失可接受 |

**结论：** Tavily 对旧工具的覆盖率达 **90% 以上**，缺失的场景（截图、OG、JSON-LD）在 LLM Agent 使用中并非核心需求，无需额外补充。

---

## 四、新工具设计

### 4.1 工具清单

| 工具名 | Tavily 方法 | 优先级 | 说明 |
|--------|-------------|--------|------|
| `tavily_search` | `client.search()` | **P0** | 替代 `smart_search`，搜索入口 |
| `tavily_extract` | `client.extract()` | **P0** | 替代 `scrape_webpage`，URL 内容提取 |
| `tavily_research` | `client.research()` | **P1** | 新增深度研究报告能力 |
| `tavily_crawl` | `client.crawl()` | **P2** | 新增站点爬取能力 |
| `tavily_map` | `client.map()` | **P2** | 新增站点发现能力 |

### 4.2 工具定义

#### `tavily_search`

```python
class TavilySearchInput(BaseModel):
    query: str = Field(description="搜索关键词（400 字符以内）")
    max_results: int = Field(default=5, ge=1, le=20, description="返回结果数")
    search_depth: str = Field(default="basic", description="搜索深度: ultra-fast / fast / basic / advanced")
    time_range: str | None = Field(default=None, description="时间范围: day / week / month / year")
    include_domains: list[str] | None = Field(default=None, description="限定搜索的域名列表")
    exclude_domains: list[str] | None = Field(default=None, description="排除的域名列表")
    include_answer: bool = Field(default=False, description="是否包含 AI 摘要回答")
    include_raw_content: bool = Field(default=False, description="是否包含全文内容")
```

**返回值：** `{ query, answer, results: [{ url, title, content, score, raw_content }], response_time }`

---

#### `tavily_extract`

```python
class TavilyExtractInput(BaseModel):
    urls: list[str] = Field(description="目标 URL 列表（最多 20 个）")
    extract_depth: str = Field(default="basic", description="提取深度: basic / advanced（JS 渲染页用 advanced）")
    query: str | None = Field(default=None, description="定向提取关键词，仅返回相关片段")
    chunks_per_source: int | None = Field(default=None, ge=1, le=5, description="每源返回片段数（需配合 query）")
```

**返回值：** `{ results: [{ url, title, raw_content(markdown), images }], failed_results, response_time }`

---

#### `tavily_research`

```python
class TavilyResearchInput(BaseModel):
    query: str = Field(description="研究主题")
    model: str = Field(default="auto", description="模型: mini（快速）/ pro（全面）/ auto（自动）")
    citation_format: str = Field(default="numbered", description="引用格式: numbered / mla / apa / chicago")
```

**返回值：** `{ request_id, status, content(研究报告含引用), sources }`

---

#### `tavily_crawl`

```python
class TavilyCrawlInput(BaseModel):
    url: str = Field(description="起始 URL")
    max_depth: int = Field(default=2, ge=1, le=5, description="最大爬取深度")
    max_breadth: int = Field(default=5, ge=1, le=50, description="每层最大宽度")
    limit: int = Field(default=50, ge=1, le=500, description="最大页面数")
    instructions: str | None = Field(default=None, description="语义聚焦指令")
    extract_depth: str = Field(default="basic", description="提取深度")
```

---

#### `tavily_map`

```python
class TavilyMapInput(BaseModel):
    url: str = Field(description="目标域名/URL")
    limit: int = Field(default=50, ge=1, le=500, description="最大返回 URL 数")
```

---

### 4.3 文件结构

```python
skills/network/tavily/
├── __init__.py              # 工具导出
├── skill_search.py          # tavily_search
├── skill_extract.py         # tavily_extract
├── skill_research.py        # tavily_research
├── skill_crawl.py           # tavily_crawl
└── skill_map.py             # tavily_map
```

---

## 五、实施计划

### Phase 1 — P0 工具实现（搜索 + 提取）

目标：`tavily_search` 和 `tavily_extract` 可工作，覆盖旧工具全部日常场景。

#### 步骤

1. **新增 `TAVILY_API_KEY` 到环境配置**
   - 文件：`config/settings.py`
   - 添加 `tavily_api_key: str` 配置项
   - `.env.example` 添加 `TAVILY_API_KEY`

2. **创建 Tavily 工具包**
   - `skills/network/tavily/__init__.py` — 统一导出 5 个工具类
   - `skills/network/tavily/skill_search.py` — `TavilySearchSkill(SkillBase)`
   - `skills/network/tavily/skill_extract.py` — `TavilyExtractSkill(SkillBase)`
   - 工具内部使用 `tavily.TavilyClient` 直连 API，不依赖 CLI

3. **注册新工具**
   - `skills/__init__.py`:
     - 新增导入 `TavilySearchSkill` / `TavilyExtractSkill`
     - 保留旧工具注册（双轨运行期）
   - 等旧工具确定可移除时再删除其注册

4. **新增数据提取器**
   - `api/callbacks/tool_extractors.py`:
     - `@register("tavily_search")` — 提取 query, answer, results 列表
     - `@register("tavily_extract")` — 提取 urls, title, raw_content

5. **新增前端气泡组件**
   - `TavilySearchBubble.vue` — 黑白简约风格，参考 `SearchBubble.vue` 的结构但精简
     - 查询栏 + 结果列表（标题/URL/片段/分数）
     - 折叠全文内容展示
     - AI 回答横幅（如有 `answer`）
   - `TavilyExtractBubble.vue` — 同样黑白简约
     - URL 信息卡片
     - Markdown 正文展示区（折叠/展开）
     - 多 URL Tab 切换

6. **更新前端注册表**
   - `registry.ts`:
     - 新增 `'tavily_search': TavilySearchBubble`
     - 新增 `'tavily_extract': TavilyExtractBubble`

#### 验证清单

- [ ] `tavily_search("2026年AI Agent框架")` 返回结构化结果，气泡正确渲染
- [ ] `tavily_search(query="...", include_raw_content=true)` 含全文
- [ ] `tavily_search(query="...", time_range="week")` 按时间过滤
- [ ] `tavily_extract(urls=[...])` 返回 Markdown 正文
- [ ] `tavily_extract(urls=[...], query="API")` 定向返回相关片段
- [ ] 旧 `smart_search` 和 `scrape_webpage` 仍然可用（双轨期）

---

### Phase 2 — 双轨运行 + 旧工具退役

目标：两个 P0 新工具经充分验证后，删除旧工具。

#### 步骤

1. **双轨验证期**（至少 3 天实际使用）
   - 日常用新工具替代旧工具
   - 确认无功能缺口

2. **删除旧搜索工具**
   - `skills/__init__.py`: 移除 `SmartSearchSkill` 导入和实例化
   - 删除文件：`skills/network/skill_search.py`
   - `tool_extractors.py`: 删除 `_extract_smart_search` 函数
   - `registry.ts`: 删除 `'smart_search': SearchBubble`
   - 可删除文件：`SearchBubble.vue`

3. **删除旧抓取工具**
   - `skills/__init__.py`: 移除 `WebScraperSkill` 导入和实例化
   - 删除文件：`skills/network/skill_scraper.py`
   - 可选删除：`skills/network/browser_manager.py`（如无其他依赖）
   - `tool_extractors.py`: 删除 `_extract_scrape` 函数
   - `registry.ts`: 删除 `'scrape_webpage': ScraperBubble`
   - 可删除文件：`ScraperBubble.vue`

#### 验证清单

- [ ] 旧工具名在 Agent 系统提示词中不再出现
- [ ] `smart_search` 调用返回工具不存在错误（正常）
- [ ] `scrape_webpage` 调用返回工具不存在错误（正常）
- [ ] 前端不再加载 `SearchBubble.vue` 和 `ScraperBubble.vue`

---

### Phase 3 — P1/P2 工具扩展（可选）

目标：新增深度研究、爬取、站点发现能力。

#### 步骤

1. **`tavily_research`**
   - 异步轮询模式（research 请求需要 30-120s）
   - 前端气泡展示进度条 + 最终报告
   - 数据提取器返回 `content`（Markdown 报告）、`sources`（引用源列表）

2. **`tavily_crawl` + `tavily_map`**
   - 批量操作，结果较大
   - 前端气泡展示统计摘要 + 可展开详情
   - 注意 Token 预算：crawl 结果可能很大，需截断或摘要后再返回

---

## 六、架构变更详情

### 6.1 新增配置文件

```python
# config/settings.py
class Settings(BaseSettings):
    # ... 现有配置 ...
    tavily_api_key: str = Field(default="", validation_alias="TAVILY_API_KEY")
```

### 6.2 工具实现模式

所有 Tavily 工具统一使用 `tavily-python` SDK（已安装 `tavily-python==0.7.26`），在工具初始化时创建客户端：

```python
from tavily import TavilyClient
from skills.base import SkillBase

class TavilySearchSkill(SkillBase):
    name: str = "tavily_search"
    description: str = "使用 Tavily 执行网络搜索..."
    args_schema = TavilySearchInput

    # 客户端懒加载
    _client: TavilyClient | None = None

    @property
    def client(self) -> TavilyClient:
        if self._client is None:
            from config.settings import get_settings
            self._client = TavilyClient(api_key=get_settings().tavily_api_key)
        return self._client
```

### 6.3 前端气泡设计原则

- **黑白简约风** — 延续 Miso 偏好的极简线框风格
- **搜索结果** — 类 `SearchBubble.vue` 结构但更精简：
  - 查询栏（query + 结果数 + 耗时）
  - AI 回答横幅（如有 `answer`）
  - 结果卡片：标题（链接）、URL、片段、相关度分数、时间
- **提取结果** — 类 `ScraperBubble.vue` 但聚焦正文：
  - URL 信息卡片
  - Markdown 正文预览（默认折叠至 2000 字符，可展开）
  - 多 URL Tab 切换

### 6.4 API Key 安全

- `TAVILY_API_KEY` 通过 `.env` 加载，与现有 `DEEPSEEK_API_KEY` 同级
- `providers.yaml` 不存储 Tavily 凭据（独立配置，非 LLM 提供商）
- 沙盒内 Python 代码可以读取 `os.environ["TAVILY_API_KEY"]`（与旧 `smart_search` 的 UAPI key 暴露风险同级别）

---

## 七、Tavily Anthropic Skills 处理

现有的 8 个 Tavily SKILL.md 文件（`tavily-search`、`tavily-extract`、`tavily-cli`、`tavily-crawl`、`tavily-dynamic-search`、`tavily-map`、`tavily-research`、`tavily-best-practices`）在工具晋升为原生 Tool 后：

| Skill | 处理方式 |
|-------|---------|
| `tavily-search` | 删除 skill — 功能已由 `tavily_search` 工具覆盖 |
| `tavily-extract` | 删除 skill — 功能已由 `tavily_extract` 工具覆盖 |
| `tavily-research` | 保留至 Phase 3 工具实现后删除 |
| `tavily-crawl` | 保留至 Phase 3 工具实现后删除 |
| `tavily-map` | 保留至 Phase 3 工具实现后删除 |
| `tavily-cli` | 删除 — 后端工具使用 SDK 而非 CLI |
| `tavily-dynamic-search` | 删除 — 动态搜索模式理念继承至工具设计 |
| `tavily-best-practices` | 删除 — 引用文档，工具实现后再无保留必要 |

> **注意：** 删除 skill 前需从 `agent/prompts.py` 的 `_scan_anthropic_skills()` 确认对应 SKILL.md 不再被扫描。该函数遍历目录时自动跳过已删除的目录，无需手动修改代码。

---

## 八、回滚方案

若 Tavily 替换后出现不可接受的问题：

1. **保留旧工具注册** — Phase 1 不删除旧工具，前端和提取器均保留
2. **双轨并行** — Agent 可自由选择新旧工具
3. **一键回滚** — 删除新工具注册 + 恢复旧工具注册即可还原

---

## 七、三管方案：Tavily 在 Jet 中的三层使用模式

Tavily 的能力在 Project Jet 中以三个层面暴露，覆盖从"随手一搜"到"深度调研"的全部场景。

### 7.1 第一管：`tavily_search` 紧凑模式（日常搜索）

**工具性质：** 原生 Tool，由 Agent 直接调用。

**行为：** 默认 `include_raw_content=False`，只返回标题、URL、摘要片段、相关度分数。Agent 收到约 800-1500 tokens 的结果摘要，足以判断搜索结果的质量。

**适用场景：**
- 日常信息检索（"搜一下最近的科技新闻"）
- 知识点快速查证（"Python 3.13 什么时候发布的"）
- 链接发现（"找找关于这个话题的文章"）

**典型调用：**

```python
# Agent 直接调用，紧凑返回
tavily_search("2026 AI Agent 框架对比", max_results=5)
# → 返回 5 条 { title, url, snippet, score }，无全文
```

**为什么这么做：** 不需要全文的场景就不带回全文。100 次搜索里可能有 80 次只看个标题和摘要就够了，剩下 20 次需要深挖的，走第二管或第三管。

---

### 7.2 第二管：`tavily_extract` 定点深挖（精准获取）

**工具性质：** 原生 Tool，由 Agent 在看了搜索结果后调用。

**行为：** 针对第一管返回的具体 URL，用 `tavily_extract` 拉取全文 Markdown。支持一次最多 20 个 URL，支持 `query` 参数定向提取相关片段。

**适用场景：**
- 看完标题后觉得某篇文章有价值，想看全文
- 多篇文章对照阅读
- 从已知 URL 提取正文内容（替代 `scrape_webpage`）

**典型调用：**

```python
# 第一管发现结果[0]、[3]、[5] 值得细看
tavily_extract(
    urls=[results[0].url, results[3].url, results[5].url],
    extract_depth="basic"
)
# → 返回 3 篇完整 Markdown 正文
```

**迭代流程：**

```
Round 1: tavily_search("quantum computing 2026")
             ↓ Agent 浏览标题
Round 2: tavily_extract(urls=[...选中的 2-3 篇...])
             ↓ Agent 阅读全文
```

---

### 7.3 第三管：`run_python` + Tavily SDK 沙盒内操作（深度调研）

**工具性质：** 利用已有的 `run_python` 工具，在其隔离沙盒中运行 Tavily Python SDK，实现多轮迭代、数据留存、动态过滤。

**行为：** Agent 编写 Python 代码，在沙盒中：
1. 调用 Tavily SDK 执行搜索
2. 将完整结果（含全文）保存在沙盒的 `/tmp/` 文件系统中
3. 仅将过滤后的摘要 `print()` 回上下文
4. 下一轮可读取 `/tmp/` 中的中间结果继续处理

**适用场景：**
- 多关键词组合搜索（"分别搜 A、B、C 三个方向"）
- 需要动态过滤规则的研究（"提取包含特定财务数据的段落"）
- 多轮迭代调研（"先搜→看标题→再搜更具体的"）
- 大规模数据采集后本地过滤

**典型调用：**

```python
# Round 1：搜索并暂存，仅打印标题
import os, json
from tavily import TavilyClient
client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

data = client.search("solid-state battery 2026", max_results=8,
                     include_raw_content=True, search_depth="advanced")
with open('/tmp/results.json', 'w') as f:
    json.dump(data, f)

for r in data['results']:
    print(f"[{r['score']:.2f}] {r['title']}")
    print(f"    {r['url']}")
    print(f"    {r['content'][:150]}")
    print()
```

```
Agent 上下文进账：~800 tokens             ← 只看到标题
300K 的全文内容：留在 /tmp/results.json     ← 不污染上下文
```

```python
# Round 2：读取保存的结果，按关键词过滤正文
import json

data = json.load(open('/tmp/results.json'))

for i, r in enumerate(data['results']):
    raw = r.get('raw_content', '') or ''
    # 只提取包含商业化相关段落的文本
    paragraphs = [p for p in raw.split('\n\n')
                  if any(kw in p.lower() for kw in
                         ['toyota', 'quantumscape', 'commercializ', 'production'])
                  and len(p) > 80]
    if paragraphs:
        print(f"## {r['title']}")
        for p in paragraphs[:3]:
            print(p)
            print()
```

```
Agent 上下文进账：~600 tokens 的过滤后信号   ← 只看到精华
```

**第三管的威力：**

| 维度 | 第一/二管 | 第三管 |
|------|----------|--------|
| 数据暂存 | 无，每次调用独立 | `/tmp/` 可跨轮次共享 |
| 过滤规则 | 固定的工具参数 | 动态 Python 代码，每次可不同 |
| 并行搜索 | 不支持 | 可同时搜索多组关键词 |
| 上下文效率 | 不错 | 极致（100-200x 压缩比） |
| 灵活性 | 受限于工具接口 | 完整的 Python 灵活性 |

### 7.4 三管之间的关系

```
日常随手一搜 ──────────────────────────────→ 第一管：tavily_search（紧凑）
       │
       ├─ 想看看某篇文章 ──────────────────→ 第二管：tavily_extract（定点）
       │
       └─ 需要深度调研、多轮迭代、动态过滤 ──→ 第三管：run_python + SDK（沙盒）
```

三管不是互斥的，而是同一个 Tavily 基础设施在不同粒度上的暴露：
- **第一管** 给 Agent 最轻量的搜索入口
- **第二管** 给 Agent 精准的内容提取能力
- **第三管** 给 Agent 完整的编程式数据操作能力

它们共享同一个 API Key 配置，同一个 `tavily-python` SDK，同一个计费池。

---

## 八、沙盒环境变量说明

> **状态：无需额外配置。** `run_python` 沙盒共享宿主进程的完整环境变量，`TAVILY_API_KEY` 设置后沙盒内 `os.environ["TAVILY_API_KEY"]` 直接可用。第三管的代码可以直接调用 `TavilyClient()`（自动读取环境变量）或 `TavilyClient(api_key=os.environ["TAVILY_API_KEY"])`。

---

## 九、与 CLI 版 dynamic-search Skill 的对比

Jet 的三管方案本质上是对 `tavily-dynamic-search` SKILL.md 中描述的 dynamic-search 模式的**再实现和升级**：

| 能力 | CLI 版（旧 Skill） | Jet 第三管（新 Tool） |
|------|-------------------|---------------------|
| 搜索方式 | `subprocess.check_output(['tvly', ...])` | `client.search()` — 直接 SDK 调用 |
| 输出解析 | JSON 字符串 → `json.loads()` | 原生 Python 对象 |
| 错误处理 | 需手动 catch `CalledProcessError` | 标准 Python 异常 |
| 跨轮次状态 | 文件 `json.dump(open('/tmp/...'))` | 同上（一致） |
| 上下文保护 | `print()` 仅输出信号 | 同上（一致） |
| 工具依赖 | `tvly` CLI（需额外安装） | `tavily-python` SDK（P0 已安装） |
| 学习成本 | 需理解 `tvly` CLI + 子进程调用 | 纯 Python，直觉友好 |

**所以第三管其实是 dynamic-search 的"原生 Python 升级版"**——保留了多轮迭代和数据暂存的核心思想，但去掉了 CLI 中间层，更干净、更可控。

---

## 附录 A：新旧工具参数对照速查

### 搜索

| 功能 | `smart_search` | `tavily_search` |
|------|---------------|----------------|
| 基本搜索 | `query` | `query` |
| 结果数 | 固定（聚合服务决定） | `max_results`（1-20） |
| 相关度 | ❌ 无 | `search_depth`（4 档） |
| 时间筛选 | ❌ 无 | `time_range`（day/week/month/year） |
| 域白名单 | `site`（单域名） | `include_domains`（多域名列表） |
| 域黑名单 | ❌ 无 | `exclude_domains` |
| 全文内容 | ❌ 需另调 `scrape_webpage` | `include_raw_content=true` |
| AI 摘要 | ❌ 无 | `include_answer=true` |
| 文件类型 | `filetype` | ❌ 无（低频忽略） |

### 抓取

| 功能 | `scrape_webpage` | `tavily_extract` |
|------|-----------------|------------------|
| 单页提取 | `url` | `urls` |
| 批量提取 | ❌ 逐页 | ✅ 最多 20 URL/次 |
| 输出格式 | HTML | Markdown |
| JS 渲染 | 浏览器渲染 | `extract_depth="advanced"` |
| 定向提取 | ❌ 全量 | `query` 参数筛选相关片段 |
| 截图 | 支持（base64） | ❌ |
| OG/JSON-LD | 完整提取 | ❌（Markdown 包含） |
| 响应速度 | 5-15 秒（浏览器启动 + 渲染） | 0.5-5 秒（API 直呼） |
