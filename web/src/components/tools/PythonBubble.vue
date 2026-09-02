<template>
  <BubbleChrome :tool-call="toolCall">
    <!-- 运行中：有实时输出则流式渲染（tool_stream 逐条累积），否则显示占位文案。
         执行前确认门控已由 ToolBubbleRouter 以通用 ConfirmBubble 统一处理，
         此处不再内联确认块。 -->
    <div v-if="toolCall.status === 'running'" class="bubble-running py-running">
      <pre
        v-if="liveStdout"
        ref="liveOutEl"
        class="py-stdout"
      >{{ liveStdout }}</pre>
      <span v-else>正在执行代码...</span>

      <!-- 中途停止：与批准执行菜单同构——截止信息整行在下，按钮右下对齐 -->
      <div class="py-section py-stop-section">
        <div class="py-section-header">
          <span class="py-section-label">✏️ 截止信息（可选）</span>
        </div>
        <input
          v-model="stopMessage"
          class="py-stop-input"
          type="text"
          placeholder="输入传给 Agent 的截止信息（可留空），回车或点击停止…"
          :disabled="stopping"
          @keyup.enter="stopExecution"
        />
      </div>
      <div class="py-stop-actions">
        <button
          class="btn-action btn-stop"
          :disabled="stopping"
          @click="stopExecution"
        >
          <span v-if="stopping">停止中…</span>
          <span v-else>停止执行</span>
        </button>
      </div>
    </div>

    <!-- 错误 -->
    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '执行失败' }}
    </div>

    <!-- 完成 -->
    <template v-else-if="toolCall.status === 'done'">
      <!-- 中途停止横幅 -->
      <div v-if="isInterrupted" class="py-interrupted-banner">
        已中途停止{{ userMessageText ? `：${userMessageText}` : '' }}
      </div>

      <div class="py-section">
        <div class="py-section-header">
          <span class="py-section-label">📝 代码</span>
          <button class="py-copy-btn" @click.stop="copyCode">复制</button>
        </div>
        <div class="py-code-block" v-html="highlightedCode"></div>
      </div>

      <div v-if="stdout" class="py-section">
        <div class="py-section-header">
          <span class="py-section-label">📤 输出</span>
          <span class="py-stdout-lines">{{ stdoutLineCount }} 行</span>
        </div>
        <pre class="py-stdout">{{ stdout }}</pre>
      </div>

      <div v-if="!code" class="raw-output">{{ toolCall.output }}</div>
    </template>
  </BubbleChrome>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { ToolCall } from '@/types'
import BubbleChrome from './_shared/BubbleChrome.vue'
import { highlightPython } from '@/utils/python-highlight'

const props = defineProps<{ toolCall: ToolCall }>()
const emit = defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

// 中途停止状态：点击后置 stopping 禁用输入与按钮，防止重复发送
const stopping = ref(false)
const stopMessage = ref('')

// 每个新工具调用重置停止状态（防止组件复用残留）
watch(() => props.toolCall.callId, () => {
  stopping.value = false
  stopMessage.value = ''
})

const isInterrupted = computed(() => {
  return props.toolCall.toolData?.interrupted === true
})

const userMessageText = computed(() => {
  const m = props.toolCall.toolData?.user_message
  return typeof m === 'string' && m ? m : ''
})

function stopExecution() {
  if (stopping.value || !props.toolCall.callId) return
  stopping.value = true
  emit('action', {
    action: 'run_python_interrupt',
    data: {
      callId: props.toolCall.callId,
      message: stopMessage.value.trim(),
    },
  })
}

/** 实时输出缓冲（tool_stream 累积，仅 running 期间有值） */
const liveStdout = computed(() => props.toolCall.stream ?? '')

// 实时输出容器高度受限（200px），每条新输出到达时滚动到底部
const liveOutEl = ref<HTMLElement | null>(null)
watch(liveStdout, () => {
  void nextTick(() => {
    if (liveOutEl.value) {
      liveOutEl.value.scrollTop = liveOutEl.value.scrollHeight
    }
  })
})

const code = computed(() => {
  if (props.toolCall.interaction?.code) {
    return props.toolCall.interaction.code as string
  }
  const tdCode = props.toolCall.toolData?.code
  if (typeof tdCode === 'string' && tdCode) return tdCode
  const raw = props.toolCall.input
  try {
    const parsed = JSON.parse(raw)
    return typeof parsed.code === 'string' ? parsed.code : ''
  } catch { }
  try {
    const jsonLike = raw.replace(/'/g, '"')
    const parsed = JSON.parse(jsonLike)
    return typeof parsed.code === 'string' ? parsed.code : ''
  } catch { }
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

<style scoped>
.py-section {
  margin-bottom: 12px;
}

.py-section:last-child {
  margin-bottom: 0;
}

.py-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.py-section-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.py-stdout-lines {
  font-size: 11px;
  color: var(--text-secondary);
  font-family: 'SF Mono', 'Consolas', monospace;
}

.py-copy-btn {
  font-size: 11px;
  color: var(--text-secondary);
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 2px 8px;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.12s;
}

.py-copy-btn:hover {
  color: var(--text-primary);
  border-color: var(--accent-light);
}

.py-code-block {
  background: var(--bg-secondary);
  border-radius: 8px;
  border: 1px solid var(--border);
  padding: 10px 0;
  overflow-x: auto;
  max-height: 300px;
  overflow-y: auto;
}

.py-code-block :deep(.py-line) {
  display: flex;
  min-height: 1.55em;
  line-height: 1.55;
}

.py-code-block :deep(.py-ln) {
  width: 40px;
  flex-shrink: 0;
  text-align: right;
  padding-right: 12px;
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  color: var(--text-secondary);
  user-select: none;
}

.py-code-block :deep(.py-tokens) {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  white-space: pre;
  color: var(--text-primary);
  padding-right: 16px;
}

.py-code-block :deep(.py-kw)      { color: var(--accent); font-style: italic; }
.py-code-block :deep(.py-builtin) { color: var(--accent-light); }
.py-code-block :deep(.py-str)     { color: #40a02b; }
.py-code-block :deep(.py-comment) { color: var(--text-secondary); font-style: italic; }
.py-code-block :deep(.py-num)     { color: #fe640b; }

.py-stdout {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  color: var(--text-primary);
  background: var(--bg-secondary);
  border-radius: 8px;
  padding: 10px 14px;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 200px;
  overflow-y: auto;
}

.raw-output {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  padding: 8px 12px;
  background: var(--bg-secondary);
  border-radius: 6px;
}

.btn-action {
  padding: 8px 20px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
  border: 1px solid transparent;
}

/* ── 中途停止菜单：与批准执行菜单同构（整行输入在下，按钮右下对齐） ── */
.py-running {
  /* 覆盖 shared.css 的 .bubble-running { display: flex }——运行中要展示
     实时输出 + 停止菜单，必须是纵向堆叠而非横向排列（否则输入区会跑到
     输出的右侧）。scoped 属性选择器比全局单类选择器优先级更高。 */
  display: block;
}

.py-stop-section {
  margin-top: 14px;
}

.py-stop-input {
  width: 100%;
  padding: 10px 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 12px;
  font-family: inherit;
  color: var(--text-primary);
  box-sizing: border-box;
  transition: border-color 0.15s;
}

.py-stop-input:focus {
  outline: none;
  border-color: var(--accent);
}

.py-stop-input::placeholder {
  color: var(--text-secondary);
}

.py-stop-input:disabled {
  opacity: 0.6;
}

.py-stop-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}

.btn-stop {
  border-color: color-mix(in srgb, #000 40%, transparent);
  background: transparent;
  color: #000;
}

.btn-stop:hover:not(:disabled) {
  background: #000;
  color: #fff;
  border-color: #000;
}

.btn-stop:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* ── 已中途停止横幅 ── */
.py-interrupted-banner {
  margin-bottom: 12px;
  padding: 10px 14px;
  border: 1px solid color-mix(in srgb, #000 35%, transparent);
  border-radius: 8px;
  color: #000;
  font-size: 12px;
  font-weight: 500;
}
</style>
