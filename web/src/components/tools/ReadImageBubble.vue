<template>
  <BubbleChrome :tool-call="toolCall">
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span class="spinner"></span>
      <span>正在读取图片...</span>
    </div>

    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '读取失败' }}
    </div>

    <template v-else-if="toolCall.status === 'done'">
      <div v-if="fileInfo" class="read-image-info">
        <span class="file-icon">🖼️</span>
        <div class="file-meta">
          <span class="file-name">{{ fileInfo.file_name }}</span>
          <span class="file-detail">
            {{ formatSize(fileInfo.file_size) }}
            <span v-if="fileInfo.mime_type" class="mime-tag">{{ fileInfo.mime_type }}</span>
          </span>
        </div>
      </div>

      <div v-else class="bubble-fallback">
        {{ displayOutput }}
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

interface ImageInfo {
  file_name: string
  file_size: number
  mime_type?: string
}

const fileInfo = computed<ImageInfo | null>(() => {
  if (props.toolCall.toolData) {
    const d = props.toolCall.toolData as Record<string, unknown>
    if (d.file_name) {
      return {
        file_name: String(d.file_name),
        file_size: Number(d.file_size) || 0,
        mime_type: d.mime_type ? String(d.mime_type) : undefined,
      }
    }
  }
  if (props.toolCall.output) {
    try {
      const p = JSON.parse(props.toolCall.output)
      if (p?.data?.file_name) {
        return {
          file_name: p.data.file_name,
          file_size: p.data.file_size || 0,
          mime_type: p.data.mime_type,
        }
      }
    } catch { /* ignore */ }
  }
  return null
})

const displayOutput = computed(() => {
  if (props.toolCall.output) {
    return props.toolCall.output.length > 500
      ? props.toolCall.output.slice(0, 500) + '...'
      : props.toolCall.output
  }
  return '图片已读取'
})

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
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

.read-image-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 8px;
  margin: 4px 0;
}

.file-icon {
  font-size: 24px;
  flex-shrink: 0;
}

.file-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.file-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  word-break: break-word;
}

.file-detail {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.mime-tag {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--bg-secondary);
  color: var(--text-tertiary);
}

.bubble-fallback {
  font-size: 13px;
  color: var(--text-secondary);
  padding: 4px 0;
  font-family: 'SF Mono', 'Consolas', monospace;
}
</style>
