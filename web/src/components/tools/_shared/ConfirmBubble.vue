<template>
  <BubbleChrome :tool-call="toolCall">
    <!-- 确认表单：question + 可选代码 + 拒绝原因 + 允许/拒绝 -->
    <div v-if="toolCall.status === 'running' && !submitted" class="confirm-body">
      <div class="confirm-header">
        <span class="confirm-icon">⚙️</span>
        <span class="confirm-title">{{ question || '执行确认' }}</span>
      </div>

      <div v-if="code" class="confirm-section">
        <div class="confirm-section-header">
          <span class="confirm-section-label">📝 代码</span>
          <span class="confirm-code-length">{{ code.length }} 字符</span>
        </div>
        <div class="confirm-code-block" v-html="highlightedCode"></div>
      </div>

      <div class="confirm-section">
        <div class="confirm-section-header">
          <span class="confirm-section-label">✏️ 拒绝原因（可选）</span>
        </div>
        <textarea
          v-model="rejectionReason"
          class="confirm-reason-input"
          placeholder="如果拒绝执行，请在此说明原因（可留空）..."
          rows="3"
        ></textarea>
      </div>

      <div class="confirm-actions">
        <button class="btn-action btn-reject" @click="submitRejection">
          拒绝执行
        </button>
        <button class="btn-action btn-approve" @click="submitApproval">
          允许执行
        </button>
      </div>
    </div>

    <!-- 已提交（防重复）占位：本地 submitted 置位后、路由切换前的瞬态 -->
    <div v-else-if="toolCall.status === 'running' && submitted" class="confirm-waiting">
      <span>已提交，等待回复...</span>
    </div>
  </BubbleChrome>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ConfirmResponse, ToolCall } from '@/types'
import BubbleChrome from './BubbleChrome.vue'
import { highlightPython } from '@/utils/python-highlight'

const props = defineProps<{ toolCall: ToolCall }>()
const emit = defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

const submitted = ref(false)
const rejectionReason = ref('')

// 每个新工具调用重置提交状态（防止组件复用残留）
watch(() => props.toolCall.callId, () => {
  submitted.value = false
  rejectionReason.value = ''
})

const question = computed(() => props.toolCall.interaction?.question ?? '')
const code = computed(() => props.toolCall.interaction?.code ?? '')

const highlightedCode = computed(() => {
  if (!code.value) return ''
  return highlightPython(code.value)
})

function send(action: 'approve' | 'reject') {
  if (submitted.value) return
  submitted.value = true
  const response: ConfirmResponse = {
    action,
    reason: action === 'reject' ? rejectionReason.value.trim() : '',
  }
  emit('action', {
    action: 'user_response',
    data: {
      interactionId: props.toolCall.interaction?.interactionId,
      response,
    },
  })
}

function submitApproval() {
  send('approve')
}

function submitRejection() {
  send('reject')
}
</script>

<style scoped>
.confirm-body {
  display: block;
}

.confirm-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  padding: 10px 14px;
  background: var(--bg-secondary);
  border-radius: 8px;
  border: 1px solid var(--border);
}

.confirm-icon {
  font-size: 16px;
}

.confirm-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.confirm-section {
  margin-bottom: 12px;
}

.confirm-section:last-child {
  margin-bottom: 0;
}

.confirm-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.confirm-section-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.confirm-code-length {
  font-size: 11px;
  color: var(--text-secondary);
  font-family: 'SF Mono', 'Consolas', monospace;
}

.confirm-code-block {
  background: var(--bg-secondary);
  border-radius: 8px;
  border: 1px solid var(--border);
  padding: 10px 0;
  overflow-x: auto;
  max-height: 300px;
  overflow-y: auto;
}

.confirm-code-block :deep(.py-line) {
  display: flex;
  min-height: 1.55em;
  line-height: 1.55;
}

.confirm-code-block :deep(.py-ln) {
  width: 40px;
  flex-shrink: 0;
  text-align: right;
  padding-right: 12px;
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  color: var(--text-secondary);
  user-select: none;
}

.confirm-code-block :deep(.py-tokens) {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  white-space: pre;
  color: var(--text-primary);
  padding-right: 16px;
}

.confirm-code-block :deep(.py-kw)      { color: var(--accent); font-style: italic; }
.confirm-code-block :deep(.py-builtin) { color: var(--accent-light); }
.confirm-code-block :deep(.py-str)     { color: #40a02b; }
.confirm-code-block :deep(.py-comment) { color: var(--text-secondary); font-style: italic; }
.confirm-code-block :deep(.py-num)     { color: #fe640b; }

.confirm-reason-input {
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

.confirm-reason-input:focus {
  outline: none;
  border-color: var(--accent);
}

.confirm-reason-input::placeholder {
  color: var(--text-secondary);
}

.confirm-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 8px;
}

.confirm-waiting {
  padding: 10px 14px;
  font-size: 12px;
  color: var(--text-secondary);
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
