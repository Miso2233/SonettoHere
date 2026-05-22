<template>
  <BubbleChrome :tool-call="toolCall">
    <!-- 运行中 -->
    <div v-if="toolCall.status === 'running'" class="bubble-running">
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

<script setup lang="ts">
import { computed } from 'vue'
import type { ToolCall } from '@/types'
import BubbleChrome from './_shared/BubbleChrome.vue'
import { highlightPython } from '@/utils/python-highlight'

const props = defineProps<{ toolCall: ToolCall }>()
defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

const code = computed(() => {
  // 优先从 toolData 取完整代码（后端 ast.literal_eval 解析，不受截断影响）
  const tdCode = props.toolCall.toolData?.code
  if (typeof tdCode === 'string' && tdCode) return tdCode
  // 降级：解析 input 字段（可能是 JSON 或 Python repr 格式）
  const raw = props.toolCall.input
  // 先尝试 JSON
  try {
    const parsed = JSON.parse(raw)
    return typeof parsed.code === 'string' ? parsed.code : ''
  } catch { /* not JSON */ }
  // 再尝试 Python repr（单引号 → 双引号）
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
  margin-bottom: 10px;
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

/* ── 代码块 ── */
.py-code-block {
  background: #eff1f5;
  border-radius: 8px;
  border: 1px solid #ccd0da;
  padding: 10px 0;
  overflow-x: auto;
  max-height: 360px;
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
  color: #8c8fa1;
  user-select: none;
}

.py-code-block :deep(.py-tokens) {
  font-family: 'MapleMono', 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  white-space: pre;
  color: #4c4f69;
  padding-right: 16px;
}

/* Syntax colors — Catppuccin Latte */
.py-code-block :deep(.py-kw)      { color: #8839ef; font-style: italic; }
.py-code-block :deep(.py-builtin) { color: #1e66f5; }
.py-code-block :deep(.py-str)     { color: #40a02b; }
.py-code-block :deep(.py-comment) { color: #8c8fa1; font-style: italic; }
.py-code-block :deep(.py-num)     { color: #fe640b; }

/* ── 标准输出 ── */
.py-stdout {
  font-family: 'MapleMono', 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  color: var(--text-primary);
  background: var(--bg-primary);
  border-radius: 8px;
  padding: 10px 14px;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 200px;
  overflow-y: auto;
}

/* ── 降级输出 ── */
.raw-output {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  padding: 8px 12px;
  background: var(--bg-primary);
  border-radius: 6px;
}
</style>
