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
| 会话 | session 与 LLM 提供商无关 | 无法按会话选择不同模型 |

### 1.2 愿景

| 能力 | 现状 | 湾区目标 |
|------|------|---------|
| 提供商数量 | 1（DeepSeek） | 多个并存，按需切换 |
| 配置方式 | `.env` 环境变量 | 环境变量 + 配置文件 + 前端管理 |
| 模型选择 | 编译时固定 | 运行时按会话选择 |
| 前端界面 | 无提供商管理页面 | 提供商管理仪表盘 |
| API 协议 | 仅 OpenAI 兼容 | 统一 OpenAI 协议（DeepSeek / Qwen / Kimi / Minimax / OpenRouter） |

### 1.3 核心原则

1. **单一事实来源** — 所有提供商配置集中管理，不散落在 `.env` 和各模块中
2. **Provider Adapter 模式** — 每个提供商实现统一接口，核心逻辑不感知具体实现
3. **按会话选择** — 每个 session 可绑定不同提供商/模型，互不影响
4. **渐进迁移** — 不破坏现有 DeepSeek 工作流，新能力逐步叠加
5. **前端可视化管理** — 提供商配置在前端页面完成，降低运维门槛

---

## 二、架构设计

### 2.1 组件层次

```
┌─────────────────────────────────────────────────────┐
│                   Provider Registry                  │
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
│  ProviderConfigStore (YAML / env fallback)           │
└─────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│               Session → Provider 绑定                 │
│                                                     │
│  Session A ──→ DeepSeek / deepseek-chat             │
│  Session B ──→ Qwen / qwen-max                      │
│  Session C ──→ OpenRouter / claude-sonnet-4         │
└─────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│            Frontend Provider Manager                 │
│                                                     │
│  /providers  → 向导式添加（选提供商 → 填凭据 → 拉取模型）│
│  /playground → 多提供商并排对比                       │
│  session header → 当前模型切换                       │
└─────────────────────────────────────────────────────┘
```

### 2.2 后端模块

```
api/
├── providers/                 # ★ 新增：提供商适配层
│   ├── __init__.py            #    ProviderAdapter 基类
│   ├── registry.py            #    提供商注册表（按名称索引）
│   ├── store.py               #    配置存储（YAML）
│   ├── openai_adapter.py      #    OpenAI 兼容 API 通用适配器（所有提供商共用）
│   ├── openrouter_adapter.py  #    OpenRouter 专用适配器（路由/用量增强）
│   └── ...                    #    未来特殊适配器
├── routes/
│   ├── chat.py                #    修改：session 关联 provider
│   ├── sessions.py            #    修改：session provider 字段
│   └── providers.py           # ★ 新增：提供商 CRUD 路由
├── dependencies.py            # 修改：ProviderRegistry 替代单一 LLM
└── session_manager.py         # 修改：session 携带 provider 标识
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
│   ├── ChatWindow.vue         # 修改：显示当前提供商/模型
│   ├── SessionSidebar.vue     # 修改：会话卡片显示模型名
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

## 三、Provider Adapter 接口定义

```python
class ProviderAdapter(ABC):
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
    api_key_env: DEEPSEEK_API_KEY  # 引用环境变量
    base_url: https://api.deepseek.com
    models:                        # 从 API 拉取后缓存
      - deepseek-chat
      - deepseek-reasoner
    enabled: true

  - id: openrouter-main
    provider_type: openai
    label: OpenRouter
    api_key_env: OPENROUTER_API_KEY
    base_url: https://openrouter.ai/api/v1
    models:
      - openai/gpt-4o
      - anthropic/claude-sonnet-4
    enabled: false
```

---

## 四、实施阶段

### Phase 1 — Provider Registry 与 Adapter（后端基础设施）

目标：建立 Provider Registry，使后端能管理多个 LLM 提供商。

- [ ] 定义 `ProviderAdapter` 抽象基类
- [ ] 实现 `ProviderRegistry`（注册、查找、健康检查）
- [ ] 实现 `ProviderConfigStore`（YAML 文件存储 + 环境变量回退）
- [ ] 实现 `OpenAIAdapter`（兼容现有 DeepSeek 配置）
- [ ] 重构 `api/dependencies.py` 使用 Registry
- [ ] 添加 `/api/providers` CRUD 路由
- [ ] 适配 health check 支持多提供商
- [ ] 迁移 `.env` 中 DeepSeek 配置到 providers.yaml

### Phase 2 — Session-Provider 绑定

目标：每个会话可独立选择 LLM 提供商和模型。

- [ ] Session 模型添加 `provider_id` 和 `model_name` 字段
- [ ] WebSocket 握手时接受 provider 选择
- [ ] Chat 路由根据 session provider 创建对应的 LLM 实例
- [ ] 前端 Session 列表显示模型信息
- [ ] 前端会话切换时保持 provider 选择

### Phase 3 — 前端提供商管理页面 & 模型发现

目标：提供可视化的提供商配置界面，并通过 `client.models.list()` 自动发现模型。

- [ ] 创建 `/providers` 路由和 `ProviderManager.vue`
- [ ] 实现 `ProviderSetupWizard.vue`（向导式添加流程）
- 添加工作流步骤：
  1. **选择提供商** — 从预设列表（DeepSeek / Qwen / Kimi / Minimax / OpenRouter）中选择，或自定义 OpenAI 兼容端点
  2. **填写凭据** — 输入 API Key 与 Base URL（敏感字段掩码显示）
  3. **拉取模型** — 前端调用后端代理 API，后端执行 `client = OpenAI(api_key=..., base_url=...)` → `models = client.models.list()` 返回模型列表
  4. **勾选启用** — 用户从列表中选择要使用的模型（支持全选/取消）
  5. **完成** — 配置保存至 providers.yaml
- [ ] 实现 `ProviderCard.vue`（显示/启禁/删除）
- [ ] 实现 `ProviderTest.vue`（发送测试请求验证连接）
- [ ] 实现 `useProviders.ts` composable（含模型拉取 API）

### Phase 4 — Playground 多提供商对比

目标：在 Playground 页面支持多个提供商并排输出对比。

- [ ] 改造 Playground 布局，支持多列并排
- [ ] 每列独立绑定一个 provider + model
- [ ] 同步输入，独立输出
- [ ] 对比模式高亮差异（相同/不同输出）

### Phase 5 — OpenRouter 深度集成与自定义端点

目标：增强 OpenRouter 支持，并允许用户添加任意 OpenAI 兼容 API。

- [ ] `OpenRouterAdapter` — 支持 OpenRouter 特有的路由策略（claude-3.5-sonnet 等）、用量统计、fallback 配置
- [ ] 自定义端点（Custom OpenAI-compatible）— 允许用户输入任意 base URL + API key 接入未预设的提供商
- [ ] 模型列表去重与别名 — 自动合并同名模型，允许用户自定义显示名

---

## 五、数据流

### 5.1 会话创建 & 模型选择

```
用户选择 Provider/Model
       │
       ▼
前端 POST /api/sessions { provider_id: "deepseek-main", model: "deepseek-chat" }
       │
       ▼
后端创建 Session，记录 provider_id + model_name
       │
       ▼
前端 WebSocket 连接 /ws/chat/{session_id}
       │
       ▼
后端从 session 获取 provider_id → Registry 获取 Adapter → Adapter.create_llm(model)
       │
       ▼
LangGraph Agent 使用该 LLM 实例执行
```

### 5.2 提供商健康检查

```
GET /api/health
       │
       ▼
Registry.iter_adapters() → 遍历所有 enabled provider
       │
       ▼
各 Adapter.check_health() → 并行调用各提供商 API（5s timeout）
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
| 配置存储 | 数据库 / YAML / 纯 env | YAML + env fallback | 无外部依赖，与现有内存系统一致；敏感值仍走 env |
| API key 存储 | 明文 / 加密 / 仅 env 引用 | env 引用 | API key 不应落盘，配置文件只存 env 变量名 |
| 适配器协议 | langchain / 原生 OpenAI SDK | OpenAI SDK 统一 | 所有目标提供商均兼容 OpenAI API，无需多协议适配；`openai` SDK 更轻量通用 |
| Session 绑定 | 创建时固定 / 运行时切换 | 创建时固定 | 简化实现；切换等价于新会话 |
| 前端配置 | 仅读 / 读写 | 读写 | 降低运维门槛，赋予用户自主权 |

---

## 七、向后兼容

1. **现有 `.env` 配置自动导入** — 首次启动时若 `providers.yaml` 不存在，从 `.env` 读取 `DEEPSEEK_*` 并生成
2. **无 provider 选择的旧 session** — 默认使用第一个 enabled provider（= 原有 DeepSeek）
3. **API 版本化** — 新增 `/api/providers` 路由不影响现有 `/api/sessions` 等端点
4. **Playground 共存** — 原有单栏模式保留，多栏对比为新增模式
