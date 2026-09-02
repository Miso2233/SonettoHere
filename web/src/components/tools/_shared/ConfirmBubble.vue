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

      <!-- 文件工具确认：写/编辑/删除/建目录 -->
      <div v-if="isFileConfirm" class="confirm-section">
        <div class="confirm-file-card" :class="fileToneClass">
          <span class="confirm-file-icon">{{ fileIcon }}</span>
          <div class="confirm-file-info">
            <div class="confirm-file-label">{{ fileLabel }}</div>
            <div class="confirm-file-path">{{ targetPath || '（路径缺失）' }}</div>
            <div v-if="fileNote" class="confirm-file-note">{{ fileNote }}</div>
          </div>
        </div>

        <!-- 写入内容预览（file_write） -->
        <div v-if="contentPreview !== null" class="confirm-sub-section">
          <div class="confirm-section-header">
            <span class="confirm-section-label">📄 内容预览</span>
            <span class="confirm-code-length">{{ payloadContentLength }} 字符</span>
          </div>
          <pre class="confirm-file-preview">{{ contentPreview }}</pre>
        </div>

        <!-- 编辑列表（file_edit） -->
        <div v-if="editsList.length > 0" class="confirm-sub-section">
          <div class="confirm-section-header">
            <span class="confirm-section-label">✂️ {{ editsList.length }} 笔编辑</span>
          </div>
          <div class="confirm-edits-block">
            <div v-for="(e, i) in visibleEdits" :key="i" class="edit-pair">
              <div class="edit-line edit-old">− {{ e.old_string }}</div>
              <div class="edit-line edit-new">+ {{ e.new_string }}</div>
            </div>
            <div v-if="editsList.length > MAX_VISIBLE_EDITS" class="edit-more">
              …等 {{ editsList.length }} 笔
            </div>
          </div>
        </div>
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
const payload = computed(() => props.toolCall.interaction?.payload ?? {})

const highlightedCode = computed(() => {
  if (!code.value) return ''
  return highlightPython(code.value)
})

// ── 文件工具确认卡片 ──────────────────────────────────────

/** 需要文件确认卡片的工具 */
const FILE_CONFIRM_TOOLS = new Set([
  'file_write', 'file_edit', 'file_delete', 'file_create_directory',
])
const MAX_PREVIEW_CHARS = 500
const MAX_VISIBLE_EDITS = 5

const isFileConfirm = computed(() => FILE_CONFIRM_TOOLS.has(props.toolCall.name))

const fileLabel = computed(() => {
  switch (props.toolCall.name) {
    case 'file_write': return '写入文件'
    case 'file_edit': return '编辑文件'
    case 'file_delete': return '删除文件'
    case 'file_create_directory': return '创建目录'
    default: return ''
  }
})

const fileIcon = computed(() => {
  switch (props.toolCall.name) {
    case 'file_write': return '📝'
    case 'file_edit': return '✂️'
    case 'file_delete': return '🗑️'
    default: return '📁'
  }
})

const fileToneClass = computed(() => {
  switch (props.toolCall.name) {
    case 'file_delete': return 'tone-danger'
    case 'file_create_directory': return 'tone-success'
    default: return 'tone-neutral'
  }
})

const fileNote = computed(() => {
  return props.toolCall.name === 'file_delete' ? '此操作不可撤销' : ''
})

const targetPath = computed(() => {
  const p = payload.value
  return (p.file_path as string) || (p.directory_path as string) || ''
})

const payloadContentLength = computed(() => {
  const raw = payload.value.content
  return typeof raw === 'string' ? raw.length : 0
})

const contentPreview = computed<string | null>(() => {
  const raw = payload.value.content
  if (typeof raw !== 'string' || !raw) return null
  return raw.length > MAX_PREVIEW_CHARS
    ? raw.slice(0, MAX_PREVIEW_CHARS) + '\n…'
    : raw
})

interface EditItem { old_string: string; new_string: string }

const editsList = computed<EditItem[]>(() => {
  const raw = payload.value.edits
  if (typeof raw !== 'string' || !raw) return []
  try {
    const arr = JSON.parse(raw)
    if (!Array.isArray(arr)) return []
    return arr.filter((e): e is EditItem =>
      typeof e === 'object' && e != null
      && typeof (e as { old_string?: unknown }).old_string === 'string'
      && typeof (e as { new_string?: unknown }).new_string === 'string'
    )
  } catch {
    return []
  }
})

const visibleEdits = computed(() => editsList.value.slice(0, MAX_VISIBLE_EDITS))

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

/* ── 文件工具确认卡片 ── */
.confirm-file-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 8px;
  border: 1px solid var(--border);
}

.confirm-file-card.tone-neutral {
  background: var(--bg-secondary);
}

.confirm-file-card.tone-danger {
  background: #fdecea;
  border-color: #f0b4b4;
}

.confirm-file-card.tone-success {
  background: #e8f5e9;
  border-color: #b8d8b8;
}

.confirm-file-icon {
  font-size: 18px;
  line-height: 1.3;
  flex-shrink: 0;
}

.confirm-file-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.confirm-file-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.tone-danger .confirm-file-label { color: #b3261e; }
.tone-success .confirm-file-label { color: #2d6a2d; }

.confirm-file-path {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  color: var(--text-primary);
  word-break: break-all;
}

.confirm-file-note {
  font-size: 11px;
  color: #b3261e;
  font-weight: 500;
}

.confirm-sub-section {
  margin-top: 10px;
}

.confirm-file-preview {
  margin: 0;
  padding: 10px 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 260px;
  overflow-y: auto;
}

.confirm-edits-block {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 12px;
  max-height: 260px;
  overflow-y: auto;
}

.edit-pair {
  padding: 4px 0;
  border-bottom: 1px dashed var(--border);
}

.edit-pair:last-child {
  border-bottom: none;
}

.edit-line {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
}

.edit-old { color: #c0392b; }
.edit-new { color: #2e7d32; }

.edit-more {
  font-size: 11px;
  color: var(--text-secondary);
  font-style: italic;
  padding-top: 4px;
}

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
