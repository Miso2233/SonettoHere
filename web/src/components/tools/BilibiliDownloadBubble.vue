<template>
  <BubbleChrome :tool-call="toolCall">
    <!-- 下载中 -->
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>正在下载视频...</span>
    </div>

    <!-- 错误 -->
    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '下载失败' }}
    </div>

    <!-- 成功 — 有结构化数据时展示富卡片 -->
    <template v-else-if="toolCall.status === 'done'">
      <div v-if="toolCall.toolData" class="bilibili-result">
        <div class="result-top">
          <img
            v-if="toolCall.toolData.cover_url"
            :src="String(toolCall.toolData.cover_url)"
            class="video-cover"
            loading="lazy"
            referrerpolicy="no-referrer"
          />
          <div class="video-info">
            <div class="video-title">{{ toolCall.toolData.video_title || '未知标题' }}</div>
            <div class="video-meta">
              <template v-if="toolCall.toolData.quality">
                <span>{{ toolCall.toolData.quality }}</span>
                <span class="meta-sep">·</span>
              </template>
              <template v-if="toolCall.toolData.filesize_mb">
                <span>{{ toolCall.toolData.filesize_mb }} MB</span>
                <span class="meta-sep">·</span>
              </template>
              <span>{{ toolCall.elapsed }}s</span>
            </div>
          </div>
        </div>
        <div class="video-actions">
          <button class="action-btn primary" @click.stop="handleOpenLocal">
            从本地打开
          </button>
          <button
            v-if="toolCall.toolData.file_path"
            class="action-btn"
            @click.stop="handleCopyPath"
          >
            复制文件路径
          </button>
        </div>
      </div>

      <!-- 无 toolData 时降级显示原始输出 -->
      <div v-else class="bubble-section">
        <div class="bubble-section-title">结果</div>
        <pre class="raw-output">{{ toolCall.output }}</pre>
      </div>
    </template>
  </BubbleChrome>
</template>

<script setup lang="ts">
import type { ToolCall } from '@/types'
import BubbleChrome from './_shared/BubbleChrome.vue'

const props = defineProps<{ toolCall: ToolCall }>()
const emit = defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

function handleOpenLocal() {
  emit('action', {
    action: 'open-file',
    data: { path: props.toolCall.toolData?.file_path },
  })
}

function handleCopyPath() {
  const path = props.toolCall.toolData?.file_path
  if (path) {
    navigator.clipboard.writeText(String(path)).catch(() => {
      // 降级：通过 DOM 复制
      const ta = document.createElement('textarea')
      ta.value = String(path)
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    })
  }
}
</script>

<style scoped>
.bilibili-result {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-top {
  display: flex;
  gap: 12px;
}

.video-cover {
  width: 120px;
  height: 68px;
  object-fit: cover;
  border-radius: 6px;
  background: var(--bg-secondary);
  flex-shrink: 0;
}

.video-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  justify-content: center;
}

.video-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.video-meta {
  font-size: 12px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
}

.meta-sep {
  color: var(--border);
}

.video-actions {
  display: flex;
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
