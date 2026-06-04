<template>
  <BubbleChrome :tool-call="toolCall">
    <!-- 确认模式：显示代码和选择按钮 -->
    <template v-if="toolCall.status === 'running' && isConfirmMode && !submitted">
      <!-- 标题区 -->
      <div class="py-confirm-header">
        <span class="py-confirm-icon">⚙️</span>
        <span class="py-confirm-title">代码执行确认</span>
      </div>

      <!-- 代码展示区 -->
      <div class="py-section">
        <div class="py-section-header">
          <span class="py-section-label">📝 代码</span>
          <span class="py-code-length">{{ code.length }} 字符</span>
        </div>
        <div class="py-code-block" v-html="highlightedCode"></div>
      </div>

      <!-- 拒绝原因输入框（可选） -->
      <div class="py-section py-reason-section">
        <div class="py-section-header">
          <span class="py-section-label">✏️ 拒绝原因（可选）</span>
        </div>
        <textarea
          v-model="rejectionReason"
          class="py-reason-input"
          placeholder="如果拒绝执行，请在此说明原因（可留空）..."
          rows="3"
        ></textarea>
      </div>

      <!-- 确认按钮 -->
      <div class="py-confirm-actions">
        <button
          class="btn-action btn-reject"
          @click="submitRejection"
        >
          拒绝执行
        </button>
        <button
          class="btn-action btn-approve"
          @click="submitApproval"
        >
          允许执行
        </button>
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
import { computed, ref } from 'vue'
import type { ToolCall } from '@/types'
import BubbleChrome from './_shared/BubbleChrome.vue'
import { highlightPython } from '@/utils/python-highlight'

const props = defineProps<{ toolCall: ToolCall }>()
const emit = defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

const submitted = ref(false)
const rejectionReason = ref('')

const isConfirmMode = computed(() => {
  return props.toolCall.interaction?.mode === 'confirm'
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

function submitApproval() {
  submitted.value = true
  emit('action', {
    action: 'user_response',
    data: {
      interactionId: props.toolCall.interaction?.interactionId,
      response: { action: 'approve', reason: '' },
    },
  })
}

function submitRejection() {
  submitted.value = true
  emit('action', {
    action: 'user_response',
    data: {
      interactionId: props.toolCall.interaction?.interactionId,
      response: { action: 'reject', reason: rejectionReason.value.trim() },
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

<style scoped>
@font-face {
  font-family: 'MapleMono';
  src: url('/fonts/MapleMono-NF-CN-Regular.ttf') format('truetype');
  font-weight: 400;
  font-style: normal;
  font-display: swap;
}

@font-face {
  font-family: 'MapleMono';
  src: url('/fonts/MapleMono-NF-CN-Italic.ttf') format('truetype');
  font-weight: 400;
  font-style: italic;
  font-display: swap;
}

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

.py-code-length {
  font-size: 11px;
  color: var(--text-secondary);
  font-family: 'SF Mono', 'Consolas', monospace;
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
  font-family: 'MapleMono', 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  color: var(--text-secondary);
  user-select: none;
}

.py-code-block :deep(.py-tokens) {
  font-family: 'MapleMono', 'SF Mono', 'Consolas', monospace;
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
  font-family: 'MapleMono', 'SF Mono', 'Consolas', monospace;
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

.py-confirm-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  padding: 10px 14px;
  background: var(--bg-secondary);
  border-radius: 8px;
  border: 1px solid var(--border);
}

.py-confirm-icon {
  font-size: 16px;
}

.py-confirm-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.py-reason-section {
  margin-bottom: 14px;
}

.py-reason-input {
  width: 100%;
  min-height: 72px;
  padding: 10px 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 12px;
  font-family: inherit;
  color: var(--text-primary);
  resize: vertical;
  box-sizing: border-box;
  transition: border-color 0.15s;
}

.py-reason-input:focus {
  outline: none;
  border-color: var(--accent);
}

.py-reason-input::placeholder {
  color: var(--text-secondary);
}

.py-confirm-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 8px;
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

.btn-reject {
  background: var(--bg-secondary);
  border-color: var(--border);
  color: var(--text-primary);
}

.btn-reject:hover {
  border-color: var(--text-secondary);
  background: color-mix(in srgb, var(--border) 20%, transparent);
}

.btn-approve {
  background: var(--accent);
  color: #fff;
}

.btn-approve:hover {
  background: color-mix(in srgb, var(--accent) 90%, #fff);
}
</style>
