<template>
  <BubbleChrome :tool-call="toolCall">
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span class="spinner"></span>
      <span>正在处理记忆...</span>
    </div>

    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '操作失败' }}
    </div>

    <template v-else-if="toolCall.status === 'done'">
      <!-- list_memories — 列表视图 -->
      <div v-if="isListMemories && items.length" class="memory-list">
        <div class="memory-stats">共 {{ items.length }} 条记忆</div>
        <div v-for="theme in themes" :key="theme" class="theme-group">
          <div class="theme-header">{{ theme }}</div>
          <div
            v-for="item in itemsByTheme(theme)"
            :key="item.id"
            class="memory-item"
          >
            <code class="memory-id">{{ item.id.slice(0, 8) }}...</code>
            <span class="memory-desc">{{ item.description }}</span>
          </div>
        </div>
      </div>

      <!-- create/update/delete/merge — 操作结果 -->
      <div v-else-if="resultMessage" class="memory-result">
        <div class="result-icon" :class="resultIconClass"></div>
        <div class="result-text">{{ resultMessage }}</div>
        <div v-if="detailContent" class="result-detail">
          <div v-if="resultSection" class="detail-tag">{{ resultSection }}</div>
          <div v-if="resultId" class="detail-id">ID: {{ resultId }}</div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else class="bubble-empty">
        {{ fallbackText }}
      </div>
    </template>
  </BubbleChrome>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ToolCall } from '@/types'
import BubbleChrome from './_shared/BubbleChrome.vue'

const props = defineProps<{ toolCall: ToolCall }>()
const emit = defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

// ── 工具名称判断 ──
const toolName = computed(() => props.toolCall.name)
const isListMemories = computed(() => toolName.value === 'list_memories')

// ── 数据源：优先 toolData，降级到 parse output ──
const data = computed(() => {
  if (props.toolCall.toolData) return props.toolCall.toolData as Record<string, unknown>
  if (props.toolCall.output) {
    try {
      const p = JSON.parse(props.toolCall.output)
      if (p?.data) return p.data as Record<string, unknown>
    } catch { /* ignore */ }
  }
  return null
})

// ── read_memories ──
const items = computed<Array<{ id: string; description: string; theme: string }>>(() => {
  const raw = data.value?.items
  if (Array.isArray(raw)) return raw as Array<{ id: string; description: string; theme: string }>
  return []
})

const themes = computed<string[]>(() => {
  const seen = new Set<string>()
  const result: string[] = []
  for (const item of items.value) {
    if (!seen.has(item.theme)) {
      seen.add(item.theme)
      result.push(item.theme)
    }
  }
  return result
})

function itemsByTheme(theme: string) {
  return items.value.filter(i => i.theme === theme)
}

// ── 其他操作（create / update / delete / merge） ──
const resultMessage = computed(() => {
  const msg = data.value?.message
  if (typeof msg === 'string') return msg
  return null
})

const resultId = computed(() => {
  const id = data.value?.id || data.value?.kept_id
  if (typeof id === 'string') return id
  return null
})

const resultSection = computed(() => {
  const s = data.value?.section
  if (typeof s === 'string') return s
  return null
})

const detailContent = computed(() => resultId.value || resultSection.value)

const resultIconClass = computed(() => {
  const name = toolName.value
  if (name === 'create_memory') return 'icon-create'
  if (name === 'update_memory') return 'icon-update'
  if (name === 'delete_memory') return 'icon-delete'
  if (name === 'merge_memories') return 'icon-merge'
  return ''
})

const fallbackText = computed(() => {
  if (props.toolCall.output) {
    const trimmed = props.toolCall.output.length > 500
      ? props.toolCall.output.slice(0, 500) + '...'
      : props.toolCall.output
    return trimmed
  }
  return '操作完成'
})
</script>

<style scoped>
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

.bubble-empty {
  font-size: 13px;
  color: var(--text-secondary);
  padding: 4px 0;
}

/* ── 记忆列表 ── */
.memory-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.memory-stats {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 10px;
  font-weight: 500;
}

.theme-group {
  margin-bottom: 12px;
}

.theme-header {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
  padding: 4px 8px;
  background: var(--bg-secondary);
  border-radius: 4px;
  margin-bottom: 4px;
}

.memory-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 4px 8px;
  font-size: 13px;
  line-height: 1.5;
}

.memory-id {
  font-size: 10px;
  color: var(--text-secondary);
  font-family: 'SF Mono', 'Consolas', monospace;
  flex-shrink: 0;
  margin-top: 2px;
}

.memory-desc {
  color: var(--text-primary);
  word-break: break-word;
}

/* ── 操作结果 ── */
.memory-result {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 4px 0;
}

.result-icon {
  display: none;
}

.result-text {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
  line-height: 1.5;
}

.result-detail {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 2px;
}

.detail-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  font-weight: 500;
}

.detail-id {
  font-size: 11px;
  color: var(--text-secondary);
  font-family: 'SF Mono', 'Consolas', monospace;
  padding: 2px 0;
}
</style>
