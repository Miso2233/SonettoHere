# LLM 视觉能力自动检测

## 概述

保存或更新模型提供商时，后端自动检测每个模型是否具备视觉能力（多模态输入支持）。检测结果写入 `providers.yaml` 的 `model_vision` 字段，并在前端提供商管理页面和顶栏中回显。

该功能解决了两个问题：

1. **运行时意识** — 聊天时顶栏直观显示当前模型是否支持多模态输入
2. **配置可见性** — 提供商管理页面的模型列表中明确标示各模型的视觉能力

---

## 数据流

```
用户保存提供商
    │
    ▼
POST/PUT /api/providers
    │
    ▼
create_provider() / update_provider()
    ├── mgr.save_config(config)          ← 先写入基础配置
    ├── detect_vision_capabilities()      ← 并行检测每个模型
    └── mgr.save_config(config)          ← 回写 vision 结果
    │
    ▼
config/providers.yaml
    └── model_vision:
          glm-5v-turbo: true
          deepseek-v4-flash: false
    │
    ▼
前端 API 返回 → ProvidersView / ChatView 渲染
```

---

## 检测方法

### 测试图片

`api/data/SonettoTest.png` — 一张包含英文文字 "Sonetto" 的 PNG 图片。

### 检测逻辑

核心函数位于 `api/providers/vision.py`：

```
test_model_vision(provider, model_name, image_path) → bool
```

1. 调用 `provider.create_llm(model_name, temperature=0)` 创建 LLM 实例
2. 读取测试图片并做 base64 编码
3. 构造多模态 `HumanMessage`：
   ```python
   HumanMessage(content=[
     {"type": "text", "text": "What text is shown in this image? Reply with only the text."},
     {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
   ])
   ```
4. 调用 `await llm.ainvoke([message])`
5. 响应文本中包含 `"Sonetto"` → 有视觉能力（`True`）
6. 报错或不包含 `"Sonetto"` → 无视觉能力（`False`）

### 并发策略

`detect_vision_capabilities()` 使用 `asyncio.gather(*tasks, return_exceptions=True)` 并行测试所有模型。异常被当作 `False` 处理，不影响其他模型的检测。

---

## 数据模型

### ProviderConfig（`api/providers/__init__.py`）

```python
@dataclass
class ProviderConfig:
    ...
    models: list[str] = field(default_factory=list)
    model_vision: dict[str, bool] = field(default_factory=dict)  # 新增

    def to_dict(self) -> dict:
        d = asdict(self)
        if not d.get("model_vision"):    # 空字典不写入 YAML
            del d["model_vision"]
        return d
```

- `model_vision` 是可选字段，缺省为空字典（等价于全无视觉）
- `to_dict()` 在空值时排除该字段，避免 YAML 中出现 `model_vision: {}`

### YAML 存储（`config/providers.yaml`）

```yaml
providers:
- id: openrouter
  models:
  - qwen/qwen3.7-plus
  - z-ai/glm-5v-turbo
  model_vision:
    z-ai/glm-5v-turbo: true
```

### 前端类型（`web/src/types/index.ts`）

```typescript
export interface ProviderConfig {
  ...
  models: string[]
  model_vision?: Record<string, boolean>
}
```

---

## 路由层变更

### `api/routes/providers.py`

两个端点从 `def` 改为 `async def`，以支持 `await` 调用视觉检测：

```python
@router.post("/providers")
async def create_provider(body: ProviderCreateBody, request: Request):
    ...
    mgr.save_config(config)                              # 1. 写入基础配置
    if config.models and IMAGE_PATH.exists():
        vision = await detect_vision_capabilities(config, IMAGE_PATH)
        config.model_vision = vision
        mgr.save_config(config)                          # 2. 回写 vision 结果
    return config.to_dict()

@router.put("/providers/{provider_id}")
async def update_provider(provider_id: str, body: ProviderUpdateBody, request: Request):
    ...  # 同上
```

- 路由先保存基础配置，再检测，再回写——确保视觉检测失败时基础配置已持久化
- 仅在有模型且测试图片存在时才执行检测
- 视觉检测不接受前端传入的 `model_vision` 值（只读，由后端自动填充）

---

## 前端回显

### 三处显示

| 位置 | 组件 | 体现方式 |
|------|------|---------|
| 提供商卡片 | `ProvidersView.vue` | 模型名右侧 `image-cog` 🏷️ 图标 |
| 编辑表单 | `ProvidersView.vue` | 模型复选框右侧 `[视觉]` / `[无视觉]` 文字标签 |
| 顶部栏 | `ContextUsageBadge.vue` | 当前模型名右侧 `image-cog` 图标 |

### 顶部栏数据流

```
ChatInput 选择模型
    │  emit('modelChange', providerId, modelName)
    ▼
ChatView.onModelChange()
    ├── selectedProviderId = providerId
    └── selectedModelName = modelName
    │
    ▼
computed selectedModelHasVision
    └── providers.find(p.id === selectedProviderId)
          └── .model_vision?.[selectedModelName] === true
    │
    ▼
ContextUsageBadge(hasVision=selectedModelHasVision)
    └── {{ displayModelName }}<Icon name="image-cog" ... />
```

---

## 异常与边界情况

| 场景 | 行为 |
|------|------|
| 测试图片不存在 | 跳过视觉检测（`config.models and IMAGE_PATH.exists()`） |
| 单个模型调用报错 | 视为无视觉能力（`except Exception: return False`） |
| provider API key 无效 | 所有模型测试均失败，全部标记为 `false` |
| 无模型（空列表） | 跳过检测，返回空字典 |
| 现有配置升级 | 读取 YAML 时 `model_vision` 缺省为空字典，首次保存时执行检测 |
| 并发调用 | `asyncio.gather` 并行测试，`return_exceptions=True` 防止单个失败影响全局 |

---

## 相关文件

| 文件 | 角色 |
|------|------|
| `api/providers/vision.py` | **核心** — 视觉检测函数（`test_model_vision` / `detect_vision_capabilities`） |
| `api/providers/__init__.py` | 数据模型 — `ProviderConfig.model_vision` 字段 |
| `api/routes/providers.py` | 路由 — `create/update_provider` 中触发检测 |
| `api/data/SonettoTest.png` | 测试图片 |
| `web/src/views/ProvidersView.vue` | 前端 — 卡片与表单的视觉标识 |
| `web/src/components/ContextUsageBadge.vue` | 前端 — 顶栏模型名旁图标 |
| `web/src/views/ChatView.vue` | 前端 — 计算 `selectedModelHasVision` |
| `web/src/types/index.ts` | 前端类型定义 |
| `config/providers.yaml` | 持久化存储 |

---

*文档版本：v1.0 — 2026-07-02*
*对应 PR：[feat/providers: 添加 LLM 视觉能力自动检测]*
