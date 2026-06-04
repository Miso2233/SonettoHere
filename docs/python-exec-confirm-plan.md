# Python 执行工具用户确认机制实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Python 代码执行前增加用户确认环节，让用户可以查看代码并决定是否执行。

**Architecture:** 参考 ask_user 系列工具的异步交互模式，通过 interaction 模块注册待确认状态，前端显示代码和确认按钮，用户确认后再执行代码。

**Tech Stack:** Python 异步编程、FastAPI WebSocket、Vue3 组合式 API

---

## 文件结构

| 文件路径 | 职责 |
|---------|------|
| `skills/system/skill_python.py` | Python 执行工具后端逻辑 |
| `web/src/components/tools/PythonBubble.vue` | Python 工具前端气泡组件 |
| `web/src/types/index.ts` | 类型定义（新增确认模式） |

---

## 任务分解

### Task 1: 修改后端 Python 工具为异步模式

**Files:**
- Modify: `skills/system/skill_python.py`

**步骤：**

- [ ] **Step 1: 修改工具类，添加异步执行方法**

```python
"""Skill: run_python — 执行 Python 代码。"""

import asyncio
import io
import sys

from pydantic import BaseModel, Field

from api import interaction
from skills.base import SkillBase, format_error, format_success


class RunPythonInput(BaseModel):
    get_doc: bool = Field(
        default=False,
        description="设为 true 以获取使用说明和安全限制"
    )
    code: str = Field(
        default="",
        description="要执行的 Python 代码，支持多行"
    )


class RunPythonSkill(SkillBase):
    name: str = "run_python"
    description: str = (
        "在隔离环境中执行 Python 代码，返回 stdout 输出。"
        "用于计算、数据处理、文本转换。★ 首次使用请先 get_doc=true 了解安全限制。"
    )
    args_schema: type[BaseModel] = RunPythonInput

    def _run(self, get_doc: bool = False, code: str = "") -> str:
        raise NotImplementedError("run_python 仅支持异步模式")

    async def _arun(self, get_doc: bool = False, code: str = "") -> str:
        if get_doc:
            return self._load_doc()
        if not code:
            return format_error("code 不能为空")

        # 注册交互，等待用户确认
        ws = interaction.current_ws.get()
        interaction_id, future = interaction.register()

        # 向前端发送确认请求
        await ws.send_json({
            "type": "ask_user",
            "payload": {
                "tool_name": self.name,
                "question": "即将执行以下 Python 代码，是否确认执行？",
                "mode": "confirm",
                "options": ["执行", "取消"],
                "interaction_id": interaction_id,
                "code": code,
            },
        })

        try:
            answer = await future
            if answer != "执行":
                return format_error("用户取消了代码执行")

            # 用户确认后执行代码
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()

            try:
                exec(code, {"__builtins__": __builtins__})
                output = sys.stdout.getvalue()
                return format_success({"output": output} if output else {"output": "（代码执行完毕，无输出）", "code": code})
            except Exception as e:
                return format_error(f"代码执行错误: {e}")
            finally:
                sys.stdout = old_stdout
        except asyncio.CancelledError:
            return format_error("用户取消了回复")
        finally:
            interaction.cleanup(interaction_id)
```

- [ ] **Step 2: 验证语法正确性**

运行: `python -m py_compile skills/system/skill_python.py`
预期: 无输出（语法正确）

- [ ] **Step 3: 提交代码**

```bash
git add skills/system/skill_python.py
git commit -m "feat: python工具改为异步模式并添加用户确认"
```

---

### Task 2: 更新前端类型定义

**Files:**
- Modify: `web/src/types/index.ts`

**步骤：**

- [ ] **Step 1: 更新 AskUserEvent 类型，添加 code 字段**

```typescript
/** ask_user 交互工具向用户展示的问题和选项 */
export interface AskUserEvent {
  type: 'ask_user'
  payload: {
    tool_name: string
    question: string
    mode: 'qa' | 'single_choice' | 'multi_choice' | 'confirm'
    options: string[]
    interaction_id: string
    code?: string  // Python 代码确认模式专用
  }
}
```

- [ ] **Step 2: 更新 AskUserInteraction 类型**

```typescript
/** ask_user 交互工具在前端存储的交互数据 */
export interface AskUserInteraction {
  question: string
  mode: 'qa' | 'single_choice' | 'multi_choice' | 'confirm'
  options: string[]
  interactionId: string
  submitted: boolean
  code?: string  // Python 代码确认模式专用
}
```

- [ ] **Step 3: 提交代码**

```bash
git add web/src/types/index.ts
git commit -m "feat: 添加 confirm 模式和 code 字段类型定义"
```

---

### Task 3: 修改前端 useChat composable 处理 code 字段

**Files:**
- Modify: `web/src/composables/useChat.ts`

**步骤：**

- [ ] **Step 1: 更新 ask_user 事件处理逻辑**

找到 `case 'ask_user'` 部分，修改为：

```typescript
case 'ask_user': {
  const ae = event as AskUserEvent
  ch.isAwaitingUser = true
  ch._awaitingToolName = ae.payload.tool_name
  const runningTool = findRunningTool(turn.events, ae.payload.tool_name)
  if (runningTool) {
    runningTool.interaction = {
      question: ae.payload.question,
      mode: ae.payload.mode,
      options: ae.payload.options,
      interactionId: ae.payload.interaction_id,
      submitted: false,
      code: ae.payload.code,  // 添加 code 字段传递
    }
  }
  break
}
```

- [ ] **Step 2: 提交代码**

```bash
git add web/src/composables/useChat.ts
git commit -m "feat: 传递 ask_user 事件中的 code 字段"
```

---

### Task 4: 修改 PythonBubble.vue 添加确认界面

**Files:**
- Modify: `web/src/components/tools/PythonBubble.vue`

**步骤：**

- [ ] **Step 1: 修改模板部分，添加确认阶段 UI**

```vue
<template>
  <BubbleChrome :tool-call="toolCall">
    <!-- 等待用户确认 -->
    <template v-if="toolCall.status === 'running' && isConfirmMode && !submitted">
      <div class="py-confirm-header">
        <span class="py-confirm-icon">⚠️</span>
        <span class="py-confirm-title">请确认执行</span>
      </div>
      
      <!-- 代码预览区 -->
      <div class="py-section">
        <div class="py-section-header">
          <span class="py-section-label">📝 代码</span>
        </div>
        <div class="py-code-block" v-html="highlightedCode"></div>
      </div>
      
      <!-- 确认按钮 -->
      <div class="py-confirm-actions">
        <button class="btn-cancel" @click="cancelExecution">取消</button>
        <button class="btn-execute" @click="confirmExecution">执行代码</button>
      </div>
    </template>

    <!-- 运行中 -->
    <div v-else-if="toolCall.status === 'running'" class="bubble-running">
      <span>正在执行代码...</span>
    </div>

    <!-- 错误 -->
    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '执行失败' }}
    </div>

    <!-- 完成 -->
    <template v-else-if="toolCall.status === 'done'">
      <!-- 代码区 -->
      <div class="py-section">
        <div class="py-section-header">
          <span class="py-section-label">📝 代码</span>
          <button class="py-copy-btn" @click.stop="copyCode">复制</button>
        </div>
        <div class="py-code-block" v-html="highlightedCode"></div>
      </div>

      <!-- 输出区 -->
      <div v-if="stdout" class="py-section">
        <div class="py-section-header">
          <span class="py-section-label">📤 输出</span>
          <span class="py-stdout-lines">{{ stdoutLineCount }} 行</span>
        </div>
        <pre class="py-stdout">{{ stdout }}</pre>
      </div>

      <!-- 无 toolData 降级 -->
      <div v-if="!code" class="raw-output">{{ toolCall.output }}</div>
    </template>
  </BubbleChrome>
</template>
```

- [ ] **Step 2: 修改 script 部分，添加确认逻辑**

```typescript
<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ToolCall } from '@/types'
import BubbleChrome from './_shared/BubbleChrome.vue'
import { highlightPython } from '@/utils/python-highlight'

const props = defineProps<{ toolCall: ToolCall }>()
const emit = defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

const submitted = ref(false)

const isConfirmMode = computed(() => {
  return props.toolCall.interaction?.mode === 'confirm' && 
         props.toolCall.interaction?.tool_name === 'run_python'
})

const code = computed(() => {
  // 优先从 interaction 获取代码（确认阶段）
  if (props.toolCall.interaction?.code) {
    return props.toolCall.interaction.code
  }
  // 优先从 toolData 取完整代码
  const tdCode = props.toolCall.toolData?.code
  if (typeof tdCode === 'string' && tdCode) return tdCode
  // 降级：解析 input 字段
  const raw = props.toolCall.input
  try {
    const parsed = JSON.parse(raw)
    return typeof parsed.code === 'string' ? parsed.code : ''
  } catch { /* not JSON */ }
  try {
    const jsonLike = raw.replace(/'/g, '"')
    const parsed = JSON.parse(jsonLike)
    return typeof parsed.code === 'string' ? parsed.code : ''
  } catch { /* not Python repr either */ }
  return ''
})

const highlightedCode = computed(() => {
  if (!code.value) return ''
  return highlightPython(code.value)
})

const stdout = computed(() => {
  return (props.toolCall.toolData?.stdout as string) ?? ''
})

const stdoutLineCount = computed(() => {
  if (!stdout.value) return 0
  return stdout.value.split('\n').length
})

function confirmExecution() {
  submitted.value = true
  emit('action', {
    action: 'user_response',
    data: {
      interactionId: props.toolCall.interaction?.interactionId,
      response: '执行',
    },
  })
}

function cancelExecution() {
  submitted.value = true
  emit('action', {
    action: 'user_response',
    data: {
      interactionId: props.toolCall.interaction?.interactionId,
      response: '取消',
    },
  })
}

function copyCode() {
  if (!code.value) return
  navigator.clipboard.writeText(code.value).catch(() => {
    const ta = document.createElement('textarea')
    ta.value = code.value
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  })
}
</script>
```

- [ ] **Step 3: 添加确认界面样式**

```css
<style scoped>
/* ... 原有样式 ... */

/* ── 确认模式样式 ── */
.py-confirm-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: color-mix(in srgb, #f59e0b 12%, transparent);
  border-radius: 6px;
  border: 1px solid #f59e0b;
}

.py-confirm-icon {
  font-size: 18px;
}

.py-confirm-title {
  font-size: 13px;
  font-weight: 600;
  color: #92400e;
}

.py-confirm-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 12px;
}

.btn-cancel {
  padding: 6px 18px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
}

.btn-cancel:hover {
  border-color: var(--accent-light);
}

.btn-execute {
  padding: 6px 18px;
  border: none;
  border-radius: 6px;
  background: #ef4444;
  color: #fff;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
}

.btn-execute:hover {
  background: #dc2626;
}
</style>
```

- [ ] **Step 4: 提交代码**

```bash
git add web/src/components/tools/PythonBubble.vue
git commit -m "feat: PythonBubble 添加代码确认界面"
```

---

### Task 5: 测试与验证

**Files:**
- Test: 手动测试

**步骤：**

- [ ] **Step 1: 启动开发服务器**

运行: `python main.py`
预期: 服务启动成功，WebSocket 连接正常

- [ ] **Step 2: 触发 Python 代码执行**

在聊天界面发送包含 `run_python` 工具调用的消息，例如：
```
执行代码: 1+1
```

- [ ] **Step 3: 验证确认流程**

预期行为:
1. 前端显示代码预览和确认按钮
2. 点击"执行"按钮后代码执行
3. 点击"取消"按钮后显示"用户取消了代码执行"
4. 执行完成后显示输出结果

- [ ] **Step 4: 测试边界情况**

测试场景:
- 空代码 → 显示错误
- 有语法错误的代码 → 显示执行错误
- 长时间运行的代码 → 正常执行

---

## 自审查

### 1. Spec 覆盖
- ✅ Python 代码执行前显示代码
- ✅ 用户可选择执行或取消
- ✅ 使用 ask_user 系列工具的交互模式

### 2. 占位符检查
- ✅ 所有步骤包含完整代码
- ✅ 无 TBD/TODO 占位符
- ✅ 所有文件路径明确

### 3. 类型一致性
- ✅ mode 类型包含 'confirm'
- ✅ code 字段在前后端一致
- ✅ interaction 数据结构一致

---

## 执行交接

**Plan complete and saved to `docs/python-exec-confirm-plan.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session, batch execution with checkpoints

**Which approach?**