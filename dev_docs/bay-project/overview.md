# Project Bay 湾区计划 — 多 LLM 提供商支持

## 一、项目概述

**Project Bay**（湾区计划）的目标是：将 SonettoHere 从单一 DeepSeek 提供商扩展为**支持多种 LLM 后端**的基础设施，并在前端提供统一的配置与管理界面。

正如港湾（Bay）可供不同船只停泊，本项目要让不同 LLM 提供商（DeepSeek、Qwen、Kimi、Minimax、OpenRouter 等）都能便捷地接入系统。

> **协议限定**：所有提供商仅通过 **OpenAI 兼容 API**（`openai` Python SDK / `ChatOpenAI`）接入。OpenRouter 作为泛用模型网关，亦使用 OpenAI 协议。

### 1.1 现状

当前系统通过 `langchain-openai` 的 `ChatOpenAI` 直接连接 DeepSeek，所有配置硬编码在 `.env` 中，前后端均无多提供商概念：

| 层次 | 现状 | 问题 |
|------|------|------|
| 配置 | `.env` 中单一 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL` | 只能切换，无法并存 |
| 后端 | `api/dependencies.py` 中创建唯一 `ChatOpenAI` 实例 | 提供商逻辑与业务耦合 |
| 前端 | 无提供商选择 UI，所有请求发往唯一的 WebSocket | 用户无法感知或切换后端 |
| 会话 | session 与 LLM 提供商无关 | 无法按消息指定不同模型 |

### 1.2 愿景

| 能力 | 现状 | 湾区目标 |
|------|------|---------|
| 提供商数量 | 1（DeepSeek） | 多个并存，按需切换 |
| 配置方式 | `.env` 环境变量 | YAML 配置文件 + 前端管理（API key 直接写入 YAML） |
| 模型选择 | 编译时固定 | 每次消息可指定 |
| 前端界面 | 无提供商管理页面 | 提供商管理仪表盘 |
| API 协议 | 仅 OpenAI 兼容 | 统一 OpenAI 协议（DeepSeek / Qwen / Kimi / Minimax / OpenRouter） |

### 1.3 核心原则

1. **单一事实来源** — 所有提供商配置集中管理，不散落在 `.env` 和各模块中
2. **Provider 模式** — 每个提供商实现统一接口，核心逻辑不感知具体实现
3. **每次请求选择** — 每条消息独立指定提供商/模型，互不影响；Session 仅负责对话历史
4. **渐进迁移** — 不破坏现有 DeepSeek 工作流，新能力逐步叠加
5. **前端可视化管理** — 提供商配置在前端页面完成，降低运维门槛

---

## 二、架构设计

### 2.1 组件层次

```
┌─────────────────────────────────────────────────────┐
│                   Provider Manager                    │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ DeepSeek │  │  Qwen    │  │  Kimi    │          │
│  │ OpenAI   │  │ OpenAI   │  │ OpenAI   │          │
│  │ Adapter  │  │ Adapter  │  │ Adapter  │          │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘          │
│       │              │             │                  │
│  ┌────┴──────────────┴─────────────┴────┐            │
│  │   ┌──────────┐  ┌──────────┐        │            │
│  │   │ Minimax  │  │OpenRouter│        │            │
│  │   │ OpenAI   │  │ OpenAI   │        │            │
│  │   │ Adapter  │  │ Adapter  │        │            │
│  │   └────┬─────┘  └────┬─────┘        │            │
│  └────────┴──────────────┴──────────────┘            │
│                                                     │
│  ProviderConfigStore (YAML)                            │
└─────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│               Per-request LLM 路由                    │
│                                                     │
│  Msg 1 ──→ DeepSeek / deepseek-chat                 │
│  Msg 2 ──→ Qwen / qwen-max                          │
│  Msg 3 ──→ OpenRouter / claude-sonnet-4             │
└─────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│            Frontend Provider Manager                 │
│                                                     │
│  /providers  → 向导式添加（选提供商 → 填凭据 → 拉取模型）│
│  /playground → 多提供商并排对比                       │
│  ChatWindow header → LLM 选择器                        │
└─────────────────────────────────────────────────────┘
```

### 2.2 后端模块

```
api/
├── providers/                 # ★ 新增：提供商适配层
│   ├── __init__.py            #    Provider 基类
│   ├── registry.py            #    提供商注册表（按名称索引）
│   ├── store.py               #    配置存储（YAML）
│   ├── openai_provider.py      #    OpenAI 兼容 API 通用 Provider（所有提供商共用）
│   ├── openrouter_provider.py  #    OpenRouter 专用 Provider（路由/用量增强）
│   └── ...                    #    未来特殊适配器
├── routes/
│   ├── chat.py                #    修改：每次消息从 payload 解析 provider，动态创建 LLM
│   ├── sessions.py            #    （无需改动，session 不持有 provider）
│   └── providers.py           # ★ 新增：提供商 CRUD 路由
├── dependencies.py            # 修改：ProviderManager 替代单一 LLM
└── session_manager.py         #    无需改动（session 不持有 provider）
```

### 2.3 前端模块

```
web/src/
├── router/
│   └── index.ts               # 新增路由 /providers
├── views/
│   ├── PlaygroundView.vue     # 改造：多提供商并排对比
│   └── ProviderManager.vue    # ★ 新增：提供商管理页面
├── components/
│   ├── ChatWindow.vue         # 修改：添加 LLM 选择器（provider + model 下拉框）
│   ├── SessionSidebar.vue     #    无需改动（session 不绑定模型）
│   └── providers/             # ★ 新增：提供商管理子组件
│       ├── ProviderSetupWizard.vue  # 向导：选提供商 → 填凭据 → 拉取模型
│       ├── ProviderCard.vue         # 单个提供商配置卡片
│       └── ProviderTest.vue         # 连接测试组件
├── composables/
│   └── useProviders.ts        # ★ 新增：提供商 API 调用封装
└── types/
    └── index.ts               # 扩展：Provider 相关类型
```

---

## 三、Provider 接口定义

```python
class Provider(ABC):
    """所有 LLM 提供商适配器必须实现的接口"""

    @property
    def provider_name(self) -> str: ...

    def create_llm(self, model: str, **kwargs) -> BaseChatModel: ...

    async def check_health(self) -> HealthStatus: ...

    def count_tokens(self, text: str) -> int: ...

    @property
    def default_model(self) -> str: ...

    @property
    def available_models(self) -> list[str]: ...
```

### 3.1 Provider Config 存储结构

```yaml
# providers.yaml
providers:
  - id: deepseek-main
    provider_type: openai          # 所有提供商统一使用 openai 类型
    label: DeepSeek
    api_key: sk-xxxxxxxxxxxx        # API key 直接写入 YAML
    base_url: https://api.deepseek.com
    models:                        # 从 API 拉取后缓存
      - deepseek-chat
      - deepseek-reasoner
    enabled: true

  - id: openrouter-main
    provider_type: openai
    label: OpenRouter
    api_key: sk-yyyyyyyyyyyy
    base_url: https://openrouter.ai/api/v1
    models:
      - openai/gpt-4o
      - anthropic/claude-sonnet-4
    enabled: false
```

---

## 四、实施阶段

### Phase 1 — Provider Manager 与 Provider 基类（后端基础设施）

目标：建立 ProviderManager，使后端能管理多个 LLM 提供商。

- [x] 定义 `Provider` 抽象基类
- [x] 实现 `ProviderManager`（注册、查找、健康检查）
- [x] 实现 `ProviderConfigStore`（YAML 文件读写，API key 直接存储）
- [x] 实现 `OpenAIProvider`（兼容现有 DeepSeek 配置）
- [x] 重构 `api/dependencies.py` 使用 ProviderManager
- [x] 添加 `/api/providers` CRUD 路由
- [x] 适配 health check 支持多提供商
- [x] 迁移 `.env` 中 DeepSeek 配置到 providers.yaml

### Phase 2 — 每次请求动态指定 LLM

目标：每条 WebSocket 消息可独立指定 LLM 提供商和模型，同一 Session 内不同消息可使用不同模型。

- [x] WebSocket `chat` 消息体扩展 `provider_id` + `model_name` 字段
- [x] `_run_agent_turn()` 在每次 turn 开始时从消息解析 provider/model → `manager.get(provider_id).create_llm(model)`
- [x] `app_state.llm` 全局单例保留作为默认 fallback（首次启动/旧 session 向后兼容）
- [ ] 前端 ChatWindow 添加 LLM 选择器（下拉框，可选 provider + model）
- [ ] 前端选择器状态按 session 持久化（localStorage），切换时自动带入下次消息

### Phase 3 — 前端提供商管理页面 & 模型发现

目标：提供可视化的提供商配置界面，并通过 `client.models.list()` 自动发现模型。

- [x] 创建 `/providers` 路由和 `ProvidersView.vue`（单文件集成向导、卡片、测试、API 调用）
- [x] 实现向导式添加流程（内联于 ProvidersView）：
  1. **选择提供商** — 从预设列表（DeepSeek / Qwen / Kimi / Minimax / OpenRouter / Custom）中选择
  2. **填写凭据** — API Key（密文输入）与 Base URL（Preset 自动填充）
  3. **拉取模型** — 前端调用 `POST /api/providers/discover-models`，后端代理执行 `client.models.list()`
  4. **勾选模型** — 全选/取消/单独勾选
  5. **完成** — 保存至 providers.yaml
- [x] 列表页：卡片显示 + 测试连接 / 拉取模型 / 编辑 / 删除
- [x] API 封装：`api/index.ts` 新增 8 个 provider 相关方法
---

## 五、数据流

### 5.1 每次消息的 LLM 路由

```
用户在 ChatWindow LLM 选择器选定 Provider/Model
       │
       ▼
用户发送消息 → WebSocket 发送 {"type": "chat", "payload": {"message": "...", "provider_id": "deepseek-main", "model": "deepseek-chat"}}
       │
       ▼
后端 _run_agent_turn() 解析消息 payload
       │
       ▼
registry.get(provider_id).create_llm(model) → 创建本次使用的 LLM 实例
       │
       ▼
LangGraph Agent 使用该 LLM 实例执行
       │
       ▼
下一条消息可换另一个 provider/model，互不影响
```

### 5.2 提供商健康检查

```
GET /api/health
       │
       ▼
ProviderManager.iter_enabled() → 遍历所有 enabled provider
       │
       ▼
各 Provider.check_health() → 并行调用各提供商 API（5s timeout）
       │
       ▼
聚合结果：{
  "deepseek-main": { "status": "ok", "model": "deepseek-chat", "latency_ms": 320 },
  "qwen-main": { "status": "ok", "model": "qwen-max", "latency_ms": 280 },
  "openrouter-main": { "status": "error", "error": "401 Unauthorized" }
}
```

---

## 六、关键设计决策

| 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|
| 配置存储 | 数据库 / YAML / 纯 env | YAML | 无外部依赖，与现有内存系统一致；API key 直接写入 YAML |
| API key 存储 | 明文 / 加密 / 仅 env 引用 | 明文 YAML | API key 直接写入 YAML，简化实现；用户自行控制 YAML 文件权限 |
| 适配器协议 | langchain / 原生 OpenAI SDK | OpenAI SDK 统一 | 所有目标提供商均兼容 OpenAI API，无需多协议适配；`openai` SDK 更轻量通用 |
| Session 绑定 | 创建时固定 / 运行时切换 / **每次请求指定** | 每次请求指定 | Session 仅管理对话历史；每条消息独立指定 provider/model，前端选择器持久化选择状态 |
| 前端配置 | 仅读 / 读写 | 读写 | 降低运维门槛，赋予用户自主权 |

---

## 七、向后兼容

1. **`.env` 一键迁移** — 首次启动时若 `providers.yaml` 不存在，从 `.env` 读取 `DEEPSEEK_*` 并将 API key 写入 YAML
2. **无 provider 指定的消息** — 若 WebSocket `chat` 消息未携带 provider_id/model，fallback 到 `app_state.llm`（原有 DeepSeek 单例），完全向后兼容
3. **API 版本化** — 新增 `/api/providers` 路由不影响现有 `/api/sessions` 等端点
4. **Playground 共存** — 原有单栏模式保留，多栏对比为新增模式
