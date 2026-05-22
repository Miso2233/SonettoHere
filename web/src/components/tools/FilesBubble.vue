<template>
  <BubbleChrome :tool-call="toolCall">
    <!-- 运行中 -->
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>{{ runningLabel }}</span>
    </div>

    <!-- 错误 -->
    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '文件操作失败' }}
    </div>

    <!-- 完成 -->
    <template v-else-if="toolCall.status === 'done'">
      <div v-if="toolCall.toolData" class="files-result">
        <!-- ===== 读取文件 ===== -->
        <template v-if="op === 'read_file'">
          <div class="file-header">
            <span class="file-icon">&#128196;</span>
            <div class="file-header-text">
              <div class="file-name">{{ fileName }}</div>
              <div class="file-path">{{ td.file_path }}</div>
            </div>
          </div>
          <div class="file-meta">
            <span class="meta-tag" v-if="fileSize">{{ fileSize }}</span>
            <span class="meta-tag" v-if="td.encoding">{{ td.encoding }}</span>
            <span class="meta-tag" v-if="td.line_count">{{ td.line_count }} 行</span>
          </div>
          <div class="file-preview" v-if="td.content">
            <div class="preview-bar">
              <span class="preview-bar-label">内容预览</span>
              <button
                v-if="td.content"
                class="preview-action"
                @click="copyContent"
              >
                复制内容
              </button>
            </div>
            <pre class="preview-content">{{ trimmedContent }}</pre>
            <div class="preview-footer" v-if="isTruncated">
              仅显示前 {{ previewLineCount }} 行 / 共 {{ td.line_count }} 行
            </div>
          </div>
          <div class="file-actions">
            <button
              v-if="td.file_path"
              class="action-btn"
              @click="copyPath"
            >
              复制路径
            </button>
          </div>
        </template>

        <!-- ===== 写入文件 ===== -->
        <template v-else-if="op === 'write_file'">
          <div class="write-success">
            <span class="success-icon">&#10003;</span>
            <div class="write-success-text">
              <div class="write-success-title">写入成功</div>
              <div class="write-success-detail">{{ fileName }}</div>
            </div>
          </div>
          <div class="file-meta">
            <span class="meta-tag" v-if="fileSize">{{ fileSize }}</span>
            <span class="meta-tag" v-if="td.line_count">{{ td.line_count }} 行</span>
          </div>
          <div class="file-path-display">{{ td.file_path }}</div>
          <div class="file-actions">
            <button
              v-if="td.file_path"
              class="action-btn"
              @click="openFile"
            >
              打开文件
            </button>
            <button
              class="action-btn"
              @click="copyPath"
            >
              复制路径
            </button>
          </div>
        </template>

        <!-- ===== 文件列表 ===== -->
        <template v-else-if="op === 'list_directory' || op === 'search_files'">
          <div class="dir-header">
            <span class="dir-icon">&#128193;</span>
            <div class="dir-header-text">
              <div class="dir-name">{{ dirName }}</div>
              <div class="dir-path">{{ td.directory_path || td.search_directory }}</div>
            </div>
          </div>
          <div class="file-meta">
            <span class="meta-tag" v-if="td.total_items != null">
              {{ td.total_items }} 项
            </span>
            <span class="meta-tag" v-if="td.extension">
              {{ td.extension }}
            </span>
          </div>
          <div class="items-list" v-if="items.length > 0">
            <div
              v-for="(item, i) in visibleItems"
              :key="i"
              class="item-row"
            >
              <span class="item-icon">{{ item.type === 'directory' ? '&#128193;' : '&#128196;' }}</span>
              <span class="item-name">{{ item.name }}</span>
              <span class="item-size" v-if="item.size_bytes != null">{{ formatSize(item.size_bytes) }}</span>
              <span class="item-date" v-if="item.modified">{{ item.modified }}</span>
            </div>
          </div>
          <div class="items-footer" v-if="isMoreItems">
            仅展示 {{ items.length }} / 共 {{ totalItems }} 项
          </div>
          <div class="file-actions">
            <button
              v-if="td.directory_path"
              class="action-btn"
              @click="copyPath"
            >
              复制路径
            </button>
          </div>
        </template>

        <!-- ===== 其他文件操作 fallback ===== -->
        <div v-else class="raw-output">{{ JSON.stringify(toolCall.toolData, null, 2) }}</div>
      </div>

      <!-- 无 toolData 降级 -->
      <div v-else class="raw-output">{{ toolCall.output }}</div>
    </template>
  </BubbleChrome>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ToolCall } from '@/types'
import BubbleChrome from './_shared/BubbleChrome.vue'

const props = defineProps<{ toolCall: ToolCall }>()
const emit = defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

// ── 工具数据 ──
const td = computed(() => props.toolCall.toolData ?? {})

const op = computed<string>(() => {
  return (td.value.operation as string) || ''
})

const MAX_PREVIEW_LINES = 30

// ── 读取文件 ──
const fileName = computed(() => {
  return td.value.file_name || (td.value.file_path as string || '').split(/[/\\]/).pop() || '未知文件'
})

const fileSize = computed(() => {
  const bytes = td.value.size_bytes as number | undefined
  if (bytes == null) return null
  return formatSize(bytes)
})

const trimmedContent = computed(() => {
  const content = td.value.content as string | undefined
  if (!content) return ''
  const lines = content.split('\n')
  return lines.slice(0, MAX_PREVIEW_LINES).join('\n')
})

const isTruncated = computed(() => {
  const content = td.value.content as string | undefined
  if (!content) return false
  return content.split('\n').length > MAX_PREVIEW_LINES
})

const previewLineCount = computed(() => MAX_PREVIEW_LINES)

// ── 文件列表 ──
const items = computed<Array<{ name: string; type: string; size_bytes?: number; modified?: string }>>(() => {
  const raw = td.value.items as Array<Record<string, unknown>> | undefined
  return (raw ?? []) as any
})

const MAX_VISIBLE_ITEMS = 20

const visibleItems = computed(() => items.value.slice(0, MAX_VISIBLE_ITEMS))

const isMoreItems = computed(() => {
  return (td.value.total_items as number) > items.value.length
})

const totalItems = computed(() => {
  return (td.value.total_items as number) || 0
})

const dirName = computed(() => {
  const path = (td.value.directory_path as string) || (td.value.search_directory as string) || ''
  const parts = path.split('/').filter(Boolean)
  return parts[parts.length - 1] || path
})

// ── 写入文件 ──

// ── 标签 ──
const runningLabel = computed(() => {
  switch (props.toolCall.name) {
    case 'file_read': return '正在读取文件...'
    case 'file_write': return '正在写入文件...'
    case 'file_list': return '正在列出文件...'
    default: return '正在操作文件...'
  }
})

// ── 工具函数 ──
function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
}

// ── 动作 ──
function copyPath() {
  const path = td.value.file_path as string
    || td.value.directory_path as string
    || ''
  if (!path) return
  navigator.clipboard.writeText(path)
  emit('action', { action: 'copy-path', data: { path } })
}

function copyContent() {
  const content = td.value.content as string | undefined
  if (!content) return
  navigator.clipboard.writeText(content)
  emit('action', { action: 'copy-content', data: { length: content.length } })
}

function openFile() {
  const path = td.value.file_path as string | undefined
  if (!path) return
  emit('action', { action: 'open-file', data: { path } })
}
</script>

<style scoped>
/* ── 文件操作气泡内容 ── */
.files-result {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ── 文件头（读写） ── */
.file-header,
.dir-header {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.file-icon,
.dir-icon {
  font-size: 22px;
  line-height: 1.2;
  flex-shrink: 0;
}

.file-header-text,
.dir-header-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
  flex: 1;
}

.file-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  word-break: break-all;
}

.file-path,
.dir-path {
  font-size: 11px;
  color: var(--text-secondary);
  font-family: 'SF Mono', 'Consolas', monospace;
  word-break: break-all;
  opacity: 0.8;
}

.dir-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

/* ── 元信息标签 ── */
.file-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.meta-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  font-weight: 500;
}

/* ── 内容预览 ── */
.file-preview {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.preview-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.preview-bar-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.preview-action {
  font-size: 11px;
  color: var(--accent);
  background: none;
  border: none;
  cursor: pointer;
  font-family: inherit;
  padding: 2px 6px;
  border-radius: 4px;
  transition: background 0.12s;
}

.preview-action:hover {
  background: var(--bg-secondary);
}

.preview-content {
  margin: 0;
  padding: 10px 12px;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 280px;
  overflow-y: auto;
}

.preview-footer {
  font-size: 11px;
  color: var(--text-secondary);
  font-style: italic;
  text-align: center;
  padding: 2px 0;
}

/* ── 写入成功 ── */
.write-success {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #eaf6ea;
  border: 1px solid #b8d8b8;
  border-radius: 6px;
}

.success-icon {
  font-size: 18px;
  color: #3d8b3d;
  font-weight: 700;
  flex-shrink: 0;
}

.write-success-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.write-success-title {
  font-size: 14px;
  font-weight: 600;
  color: #2d5a2d;
}

.write-success-detail {
  font-size: 12px;
  color: #3d7a3d;
  word-break: break-all;
}

.file-path-display {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  color: var(--text-secondary);
  padding: 6px 10px;
  background: var(--bg-primary);
  border-radius: 4px;
  word-break: break-all;
}

/* ── 文件列表 ── */
.items-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 260px;
  overflow-y: auto;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px 0;
}

.item-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 10px;
  font-size: 13px;
  transition: background 0.1s;
}

.item-row:hover {
  background: var(--bg-secondary);
}

.item-icon {
  font-size: 15px;
  flex-shrink: 0;
  width: 20px;
  text-align: center;
}

.item-name {
  flex: 1;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
}

.item-size {
  font-size: 11px;
  color: var(--text-secondary);
  flex-shrink: 0;
  min-width: 56px;
  text-align: right;
}

.item-date {
  font-size: 11px;
  color: var(--text-secondary);
  flex-shrink: 0;
  min-width: 56px;
  text-align: right;
}

.items-footer {
  font-size: 11px;
  color: var(--text-secondary);
  font-style: italic;
  text-align: center;
  padding: 2px 0;
}

/* ── 动作按钮 ── */
.file-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: 12px;
  cursor: pointer;
  font-family: inherit;
  transition: background 0.12s, border-color 0.12s;
}

.action-btn:hover {
  background: var(--bg-secondary);
  border-color: var(--accent-light);
}

/* ── 运行中 / 错误 / 降级 ── */
.bubble-running {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  flex-shrink: 0;
}

@keyframes spin { to { transform: rotate(360deg); } }

.bubble-error {
  font-size: 13px;
  color: #b91c1c;
  padding: 4px 0;
}

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
