<template>
  <BubbleChrome :tool-call="toolCall">
    <!-- 运行中 -->
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>{{ runningLabel }}</span>
    </div>

    <!-- 错误（含 SonettoBlocker 特殊渲染） -->
    <SonettoBlockerError
      v-else-if="toolCall.status === 'error'"
      :output="toolCall.output"
      fallback="编辑操作失败"
    />

    <!-- 完成 -->
    <template v-else-if="toolCall.status === 'done'">
      <div v-if="toolCall.toolData" class="edit-result">
        <!-- ===== 替换 ===== -->
        <template v-if="op === 'edit'">
          <div class="edit-summary success-banner">
            <span class="banner-icon">&#9998;</span>
            <div class="banner-text">
              <div class="banner-title">替换成功</div>
              <div class="banner-detail">{{ td.file_path }}</div>
            </div>
          </div>
          <div class="edit-meta">
            <span class="meta-tag">{{ td.replaced_count }} 处匹配已替换</span>
            <span class="meta-tag" v-if="td.replace_all">全部替换</span>
          </div>
          <div class="file-actions">
            <button class="action-btn" @click="copyPath">复制路径</button>
          </div>
        </template>

        <!-- ===== 读取 ===== -->
        <template v-else-if="op === 'read'">
          <div class="file-header">
            <span class="file-icon">&#128196;</span>
            <div class="file-header-text">
              <div class="file-name">{{ fileName }}</div>
              <div class="file-path">{{ td.file_path }}</div>
            </div>
          </div>
          <div class="edit-meta">
            <span class="meta-tag">共 {{ td.total_lines }} 行</span>
            <span class="meta-tag" v-if="td.offset > 0">从第 {{ td.offset + 1 }} 行起</span>
          </div>
          <div class="file-content" v-if="lines.length > 0">
            <div v-for="(line, i) in visibleLines" :key="i" class="code-line">
              <span class="line-num">{{ line.num }}</span>
              <span class="line-text">{{ line.content }}</span>
            </div>
            <div class="lines-footer" v-if="isMoreLines">
              仅显示前 {{ MAX_VISIBLE_LINES }} 行 / 共 {{ td.total_lines }} 行
            </div>
          </div>
          <div class="file-actions">
            <button class="action-btn" @click="copyContent">复制内容</button>
            <button class="action-btn" @click="copyPath">复制路径</button>
          </div>
        </template>

        <!-- ===== 多笔编辑 ===== -->
        <template v-else-if="op === 'multi_edit'">
          <div class="multi-summary" :class="multiClass">
            <span class="multi-icon">{{ multiIcon }}</span>
            <div class="multi-text">
              <div class="multi-title">{{ multiTitle }}</div>
              <div class="multi-detail">{{ td.file_path }}</div>
            </div>
          </div>
          <div class="edit-meta">
            <span class="meta-tag">共 {{ td.total_edits }} 笔</span>
            <span class="meta-tag success-tag">成功 {{ td.success_count }}</span>
            <span v-if="td.failed_count > 0" class="meta-tag fail-tag">失败 {{ td.failed_count }}</span>
          </div>
          <div class="edit-results-list" v-if="multiResults.length > 0">
            <div
              v-for="(r, i) in multiResults"
              :key="i"
              class="edit-result-item"
              :class="r.status"
            >
              <span class="eri-icon">{{ r.status === 'ok' ? '&#10003;' : '&#10007;' }}</span>
              <span class="eri-index">#{{ i + 1 }}</span>
              <span class="eri-msg">{{ r.message || r.replaced_count + ' 处替换' }}</span>
            </div>
          </div>
        </template>

        <!-- ===== 搜索 ===== -->
        <template v-else-if="op === 'search'">
          <div class="search-header">
            <span class="search-icon">&#128269;</span>
            <div class="search-header-text">
              <div class="search-pattern">/{{ td.pattern }}/</div>
              <div class="search-file">{{ td.file_path }}</div>
            </div>
          </div>
          <div class="edit-meta">
            <span class="meta-tag">{{ td.total_matches }} 处匹配</span>
          </div>
          <div class="matches-list" v-if="matches.length > 0">
            <div
              v-for="(m, i) in visibleMatches"
              :key="i"
              class="match-row"
            >
              <span class="match-pos">第 {{ m.line_num }} 行</span>
              <span class="match-col">列 {{ m.column }}</span>
              <code class="match-text">{{ m.match }}</code>
            </div>
            <div class="lines-footer" v-if="isMoreMatches">
              仅显示前 {{ MAX_VISIBLE_MATCHES }} 条 / 共 {{ td.total_matches }} 条
            </div>
          </div>
          <div class="file-actions" v-else>
            <span class="no-result">无匹配结果</span>
          </div>
        </template>

        <!-- ===== fallback ===== -->
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
import SonettoBlockerError from './_shared/SonettoBlockerError.vue'

const props = defineProps<{ toolCall: ToolCall }>()
const emit = defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

// ── 工具数据 ──
const td = computed<Record<string, any>>(() => {
  if (props.toolCall.toolData) return props.toolCall.toolData as Record<string, any>
  if (props.toolCall.output) {
    try {
      const p = JSON.parse(props.toolCall.output)
      if (p?.data) return p.data as Record<string, any>
    } catch { /* ignore */ }
  }
  return {}
})

const op = computed<string>(() => (td.value.operation as string) || '')

// ── Read ──
const lines = computed<Array<{ num: number; content: string }>>(() => {
  const raw = td.value.lines
  return Array.isArray(raw) ? raw : []
})

const MAX_VISIBLE_LINES = 50
const visibleLines = computed(() => lines.value.slice(0, MAX_VISIBLE_LINES))
const isMoreLines = computed(() => (td.value.total_lines as number) > MAX_VISIBLE_LINES)

const fileName = computed(() => {
  const path = td.value.file_path as string
  return path?.split(/[/\\]/).pop() || '未知文件'
})

// ── Multi-edit ──
const multiResults = computed<Array<Record<string, any>>>(() => {
  const raw = td.value.results
  return Array.isArray(raw) ? raw : []
})

const multiClass = computed(() => {
  const failed = td.value.failed_count as number
  return failed > 0 ? 'has-failures' : 'all-success'
})

const multiIcon = computed(() => {
  return (td.value.failed_count as number) > 0 ? '&#9888;' : '&#10003;'
})

const multiTitle = computed(() => {
  const total = td.value.total_edits as number
  const success = td.value.success_count as number
  const failed = td.value.failed_count as number
  if (failed === 0) return `${total} 笔编辑全部成功`
  return `完成 ${success}/${total} 笔编辑，${failed} 笔失败`
})

// ── Search ──
const matches = computed<Array<{ line_num: number; column: number; match: string }>>(() => {
  const raw = td.value.matches
  return Array.isArray(raw) ? raw : []
})

const MAX_VISIBLE_MATCHES = 30
const visibleMatches = computed(() => matches.value.slice(0, MAX_VISIBLE_MATCHES))
const isMoreMatches = computed(() => (td.value.total_matches as number) > MAX_VISIBLE_MATCHES)

// ── 标签 ──
const runningLabel = computed(() => {
  return '正在编辑文件...'
})

// ── 动作 ──
function copyPath() {
  const path = td.value.file_path as string || ''
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
</script>

<style scoped>
.edit-result {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 4px 0;
}

/* ── 运行中 / 错误 ── */
.bubble-running {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.bubble-error {
  font-size: 13px;
  color: #b91c1c;
  padding: 4px 0;
}

/* ── 成功横幅 ── */
.success-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #e8f5e9;
  border: 1px solid #b8d8b8;
  border-radius: 8px;
}

.banner-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.banner-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
  flex: 1;
}

.banner-title {
  font-size: 14px;
  font-weight: 600;
  color: #2d5a2d;
}

.banner-detail {
  font-size: 11px;
  color: #3d7a3d;
  font-family: 'SF Mono', 'Consolas', monospace;
  word-break: break-all;
}

/* ── 元信息标签 ── */
.edit-meta {
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

/* ── 文件头 ── */
.file-header {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.file-icon {
  font-size: 22px;
  line-height: 1.2;
  flex-shrink: 0;
}

.file-header-text {
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

.file-path {
  font-size: 11px;
  color: var(--text-secondary);
  font-family: 'SF Mono', 'Consolas', monospace;
  word-break: break-all;
  opacity: 0.8;
}

/* ── 代码内容 ── */
.file-content {
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 6px;
  max-height: 320px;
  overflow-y: auto;
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
}

.code-line {
  display: flex;
  padding: 0 0;
  min-height: 22px;
}

.code-line:hover {
  background: var(--bg-secondary);
}

.line-num {
  display: inline-block;
  min-width: 44px;
  padding: 0 10px 0 12px;
  color: var(--text-secondary);
  text-align: right;
  user-select: none;
  opacity: 0.5;
  font-size: 11px;
  border-right: 1px solid var(--border);
  margin-right: 10px;
  line-height: 1.6;
}

.line-text {
  padding: 1px 0;
  white-space: pre;
  color: var(--text-primary);
}

.lines-footer {
  font-size: 11px;
  color: var(--text-secondary);
  font-style: italic;
  text-align: center;
  padding: 6px 0;
  border-top: 1px solid var(--border);
}

/* ── 多笔编辑 ── */
.multi-summary {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
}

.multi-summary.all-success {
  background: #e8f5e9;
  border: 1px solid #b8d8b8;
}

.multi-summary.has-failures {
  background: #fff3e0;
  border: 1px solid #ffe0b2;
}

.multi-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.multi-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
  flex: 1;
}

.multi-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.multi-detail {
  font-size: 11px;
  color: var(--text-secondary);
  font-family: 'SF Mono', 'Consolas', monospace;
  word-break: break-all;
}

.edit-results-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px 0;
  max-height: 200px;
  overflow-y: auto;
}

.edit-result-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 10px;
  font-size: 13px;
}

.edit-result-item.ok {
  color: #2e7d32;
}

.edit-result-item.error {
  color: #c0392b;
}

.eri-icon {
  font-size: 14px;
  flex-shrink: 0;
  width: 16px;
  text-align: center;
}

.eri-index {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  min-width: 24px;
}

.eri-msg {
  word-break: break-word;
}

/* ── 搜索 ── */
.search-header {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.search-icon {
  font-size: 18px;
  flex-shrink: 0;
  line-height: 1.3;
}

.search-header-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
  flex: 1;
}

.search-pattern {
  font-size: 14px;
  font-weight: 600;
  color: var(--accent);
  font-family: 'SF Mono', 'Consolas', monospace;
}

.search-file {
  font-size: 11px;
  color: var(--text-secondary);
  font-family: 'SF Mono', 'Consolas', monospace;
  word-break: break-all;
  opacity: 0.8;
}

.matches-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px 0;
  max-height: 280px;
  overflow-y: auto;
}

.match-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 4px 10px;
  font-size: 12px;
  font-family: 'SF Mono', 'Consolas', monospace;
}

.match-row:hover {
  background: var(--bg-secondary);
}

.match-pos {
  font-weight: 600;
  color: var(--text-secondary);
  white-space: nowrap;
  font-size: 11px;
}

.match-col {
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.match-text {
  color: var(--accent);
  word-break: break-all;
  background: rgba(255, 255, 255, 0.05);
  padding: 1px 4px;
  border-radius: 3px;
}

.no-result {
  font-size: 13px;
  color: var(--text-secondary);
  padding: 4px 0;
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

/* ── 降级 ── */
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
