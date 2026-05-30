# 工具/技能（Tool / Skill）开发指南

本文档描述从零到一开发一个新的 SonettoHere 工具/技能的完整流程。分为前端专属气泡（Kaleidoscope）之前的**基础部署**和之后的**万花筒定制**两个阶段。

---

## 总览：开发流程图

```
确定功能 → 后端原型 → 后端部署 + SKILL.md → 前端默认气泡 → 收集反馈
    ↓
Kaleidoscope 设计 → Playground 验收 → 后端 extractor → 收集反馈 → DEBUG
```

---

## 第零步：功能设计与原型验证（用户负责）

### 确定四要素

| 要素 | 说明 | 示例（tarot） |
|------|------|--------------|
| **功能** | 工具做什么 | 塔罗牌占卜（韦特塔罗 RWS） |
| **输入** | LLM 需要传什么参数 | `question`, `spread_type`, `get_doc` |
| **输出** | 返回给 LLM 和前端的数据 | 牌面数组、问题、牌阵名称 |
| **领域知识** | LLM 需要知道什么才能用 | 牌阵含义、单牌/三牌/凯尔特十字区别 |

### 原型测试

核心 Python 函数应当在 **独立脚本** 或 **Jupyter Notebook** 中以原型机形式测试通过，再搬入项目。测试覆盖：

- 各种输入下的正确输出
- 外部 API 调用的异常（超时、空结果、HTTP 错误）
- 边界条件（空字符串、缺失字段、超长输入）

### 选择工具集归属

检查已有工具集文件夹：

| 文件夹 | 领域 | 已有工具 |
|--------|------|---------|
| `skills/system/` | 系统级 | time, run_python |
| `skills/network/` | 网络服务 | weather, smart_search, scraper, holiday, image_understand |
| `skills/map/` | 地图 | nearby_search, geocode, transit, cycling, fuzzy_address |
| `skills/files/` | 文件操作 | file_ops, pdf_reader, doc_reader |
| `skills/development/` | 开发辅助 | syntax, code_quality, unit_test, debugger |
| `skills/todo/` | Todoist | add, list, complete, ... |
| `skills/entertainment/` | 娱乐 | tarot, answer_book |
| `skills/bilibili/` | B站 | download, set_cookie |
| `skills/task/` | 任务管理 | task_tracker |
| `skills/interaction/` | WebUI 交互 | ask_user_qa, ask_user_single_choice, ask_user_multi_choice |

决策：

- **功能与某文件夹已有工具共享数据和 API 依赖** → 添加到该文件夹
- **全新的独立领域** → 新建文件夹 `skills/<new-domain>/`
- **纯指导性质（仅提供文档、不调用 API）** → 每个指导类工具独立占用一个 SKILL.md，因此必须建立**自己的文件夹**，`_run` 中只返回 `get_doc`

---

## 第一步：后端部署

### 1a. 编写 Skill 类

在对应工具集文件夹下创建 `skill_<name>.py`，继承 `SkillBase`：

```python
"""Skill: <name> — <一句话描述>。"""

from pydantic import BaseModel, Field
from skills.base import SkillBase, format_success, format_error


class XxxInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")
    # ... 其他入参


class XxxSkill(SkillBase):
    name: str = "<tool_name>"              # ★ 与前端气泡注册名一致
    description: str = "..."               # LLM 看到的功能描述
    args_schema: type[BaseModel] = XxxInput

    def _run(self, get_doc: bool = False, ...) -> str:
        if get_doc:
            return self._load_doc()
        # ... 核心逻辑 ...
        return format_success({"key": "value", ...})
```

关键约定：

- `name` 使用 `snake_case`，不包含空格
- `_run` 返回 JSON 字符串：成功用 `format_success(data_dict)`，失败用 `format_error(message)`
- 支持 `get_doc=True` 模式返回 `SKILL.md`（纯指导类工具可只提供这个）
- 如需类级别的共享 HTTP 客户端，通过 `self.client` 访问 `SharedAPIClient`

### 1b. 撰写 SKILL.md

在同目录下创建 `SKILL.md`，LLM 通过 `get_doc=True` 读取。格式参考 [skills/entertainment/SKILL.md](../skills/entertainment/SKILL.md)：

- 工具的功能说明
- 参数含义和格式
- 常见陷阱或边界情况
- 使用示例

### 1c. 注册到 ALL_SKILLS

编辑 [skills/__init__.py](../skills/__init__.py)：

1. 在对应的 `# Comment` 分区下添加 import
2. 在 `return [...]` 列表中添加实例化

```python
# <Domain>
from skills.<domain>.skill_<name> import XxxSkill

return [
    ...
    XxxSkill(client=client),
    ...
]
```

### 纯指导类工具（跳过第零步）

某些技能不依赖代码，只是指导 LLM 如何完成任务的文章。此时：

- 为该工具**创建一个独立的文件夹** `skills/<guide-name>/`
- 在 `_run` 中只 `return self._load_doc()`，不调用外部 API
- SKILL.md 包含完整的指导内容
- 必须占用**自己的** SKILL.md，不能与其他工具共用文件夹

---

## 第二步：前端默认气泡部署

### 2a. 确认前后端通信

完成第一步后，工具已经在 Agent 中可用。在 WebUI 中触发该工具：

- LLM 输出会通过 WebSocket 以 `tool_start` / `tool_end` 事件推送
- 前端目前会使用 `ToolCallCard`（**默认兜底气泡**）渲染
- 检查 **WebSocket Payload** 中 `tool_name`、`output`、`tool_data` 是否正确

### 2b. 让前端注册表中存在此工具

当前端气泡注册表 `registry.ts` 中没有该工具时，`ToolBubbleRouter` 自动降级到 `ToolCallCard`。这一步**无需代码变更**，但建议验证：

```typescript
// web/src/components/tools/registry.ts
// 如果这里还没有你的工具，不需要动手——ToolCallCard 会自动兜底
```

---

## 第三步：收集用户反馈

在默认气泡下运行工具，重点检查：

- [ ] LLM 是否正确理解了输入参数并调用
- [ ] 返回值是否正确呈现
- [ ] 是否有 LLM 因缺少领域知识而错误使用
- [ ] 是否有需要调整 `description` 文本的情况

根据反馈调整 `SKILL.md` 和 `description`，直到 LLM 能够稳定正确地使用该工具。

---

## 第四步：Kaleidoscope——设计新气泡

参考 [kaleidoscope-project.md](../projects/kaleidoscope/kaleidoscope-project.md)。

### 4a. 设计气泡的三个状态

每个工具气泡需要覆盖三种状态：

| 状态 | 展示内容 |
|------|---------|
| **running**（运行中） | 加载动画/进度提示/占位信息 |
| **done**（完成） | 结构化数据展示（核心设计） |
| **error**（出现错误） | 错误提示 + 可能的恢复操作 |

### 4b. 创建气泡组件

在 `web/src/components/tools/` 下创建 `<Name>Bubble.vue`：

```vue
<template>
  <BubbleChrome :tool-call="toolCall">
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span class="spinner"></span>
      <span>正在处理...</span>
    </div>

    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '处理失败' }}
    </div>

    <template v-else-if="toolCall.status === 'done'">
      <!-- 自定义展示 -->
    </template>
  </BubbleChrome>
</template>
```

`BubbleChrome`（位于 `tools/_shared/BubbleChrome.vue`）提供统一的外壳（圆角、边框、状态图标、耗时、折叠），内容区域由各工具自由定义。

### 4c. Playground 验收

气泡必须先通过 Playground 以 **纯前端形式** 展示验收，再部署到实际 Chat：

1. 在 `PlaygroundView.vue`（`/playground` 路由）中添加该工具气泡的预览
2. 用**模拟数据**分别展示三个状态
3. 验收通过后再执行下一步

注册到 `web/src/components/tools/registry.ts`：

```typescript
import XxxBubble from './XxxBubble.vue'

const registry: Record<string, Component> = {
  ...
  '<tool_name>': XxxBubble,
}
```

---

## 第五步：后端 Extractor 部署

Kaleidoscope 气泡需要结构化数据来渲染。后端通过 `tool_data` 字段在 `tool_end` 事件中推送。在 [api/callbacks/tool_extractors.py](../api/callbacks/tool_extractors.py) 中注册提取器：

```python
@register("<tool_name>")
def _extract_xxx(
    _tool_name: str, parsed: dict[str, Any], _tool_input: str | None = None,
) -> dict[str, Any] | None:
    """返回 <字段1>, <字段2>, ..."""
    data = _get_data(parsed)
    if data is None:
        return None
    return {
        "field_one": data.get("field_one"),
        "field_two": data.get("field_two"),
    }
```

**前后端字段对齐检查**：

| 后端 `_extract_xxx` 返回的字段 | 前端 Vue 组件使用的字段 | 类型一致？ |
|-------------------------------|------------------------|-----------|
| `video_title` | `td.video_title` | ✓ |
| `cover_url` | `td.cover_url` | ✓ |

确认每个字段的名称、类型和语义在前端和后端完全一致。

---

## 第六步：收集反馈与 DEBUG

参照 `dev_docs/projects/kaleidoscope/kaleidoscope-project.md` 中的记载方案进行 DEBUG：

- 运行中状态是否有合理的加载提示？
- 完成状态的数据展示是否完整清晰？
- 错误状态是否提供了有用的诊断信息？
- 前后端字段是否匹配（`tool_data` 的 key 名、嵌套结构）？
- 是否需要为 `_get_data` 中的特殊 case 添加保护逻辑（如 `debugger` 的字符串模式）？

在 `BubbleChrome` 的 `tool-data` prop 中，`tool_data` 来自 WebSocket 的 `tool_end.tool_data`。如果渲染有问题，先在浏览器 DevTools 中检查 Network → WebSocket 消息。

---

## 清单：新工具上线 Check List

### 后端
- [ ] skill_<name>.py 实现并测试 ✅
- [ ] SKILL.md 撰写 ✅
- [ ] skills/__init__.py 注册 ✅

### 前端（基础）
- [ ] WebSocket 通信正常（tool_start / tool_end）✅
- [ ] 默认气泡（ToolCallCard）正确兜底 ✅
- [ ] LLM 可稳定调用 ✅

### 前端（Kaleidoscope）
- [ ] Playground 纯前端验收通过 ✅
- [ ] registry.ts 注册 ✅
- [ ] tool_extractors.py 注册 ✅
- [ ] 前后端字段对齐 ✅
- [ ] 三个状态覆盖 ✅
