<template>
  <!-- SonettoBlocker 阻断错误（特殊视觉） -->
  <div v-if="isBlocked" class="blocker-banner">
    <div class="blocker-header">
      <span class="blocker-shield">🛡️</span>
      <span class="blocker-title">访问已被安全阻断</span>
    </div>
    <div class="blocker-divider" />
    <div class="blocker-body">
      <p class="blocker-intro">此操作因 <strong>SonettoBlocker</strong> 安全机制被阻止：</p>

      <div v-if="blockedPaths.length" class="blocker-section">
        <div class="blocker-label">阻断位置</div>
        <div v-for="(p, i) in blockedPaths" :key="i" class="blocker-path-item">
          <span class="blocker-path-icon">📁</span>
          <code class="blocker-path-text">{{ p }}</code>
        </div>
      </div>

      <div class="blocker-notice">
        <span class="blocker-notice-icon">⚠️</span>
        <span>Agent 正在尝试访问以上路径，请等待其说明访问原因及下一步计划。</span>
      </div>
    </div>
  </div>

  <!-- 普通错误 -->
  <div v-else class="bubble-error">
    {{ displayText }}
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  output: string | null
  fallback?: string
}>()

const displayText = computed(() => props.output || props.fallback || '操作失败')

const isBlocked = computed(() => {
  return !!props.output && props.output.includes('SonettoBlocker')
})

/** 从后端错误消息中提取被阻断的目录路径 */
const blockedPaths = computed<string[]>(() => {
  if (!props.output) return []
  const lines = props.output.split('\n')
  const paths: string[] = []

  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue

    // 格式1: "  • C:\path"
    const bulletMatch = trimmed.match(/^[•\-*]\s+(.+)$/)
    if (bulletMatch) {
      const path = bulletMatch[1].trim()
      if (path) paths.push(path)
      continue
    }

    // 格式2: "在目录 "C:\path" 中发现了..."
    const dirMatch = trimmed.match(/在目录\s+"([^"]+)"/)
    if (dirMatch) {
      paths.push(dirMatch[1])
    }
  }

  return paths
})
</script>

<style scoped>
.blocker-banner {
  background: linear-gradient(135deg, #fff5f5 0%, #fff0e6 100%);
  border: 1.5px solid #e74c3c;
  border-radius: 10px;
  overflow: hidden;
}

.blocker-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px 6px;
}

.blocker-shield {
  font-size: 22px;
  flex-shrink: 0;
}

.blocker-title {
  font-size: 15px;
  font-weight: 700;
  color: #c0392b;
}

.blocker-divider {
  height: 1px;
  background: linear-gradient(to right, #e74c3c44, transparent);
  margin: 2px 16px;
}

.blocker-body {
  padding: 8px 16px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.blocker-intro {
  margin: 0;
  font-size: 13px;
  color: #7f8c8d;
  line-height: 1.5;
}

.blocker-intro strong {
  color: #c0392b;
  font-weight: 700;
}

.blocker-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.blocker-label {
  font-size: 10px;
  font-weight: 600;
  color: #e67e22;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.blocker-path-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: rgba(231, 76, 60, 0.06);
  border: 1px solid rgba(231, 76, 60, 0.15);
  border-radius: 6px;
}

.blocker-path-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.blocker-path-text {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  color: #c0392b;
  word-break: break-all;
  background: none;
  padding: 0;
}

.blocker-notice {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 12px;
  color: #e67e22;
  line-height: 1.5;
  padding: 8px 10px;
  background: rgba(230, 126, 34, 0.08);
  border-radius: 6px;
}

.blocker-notice-icon {
  flex-shrink: 0;
  font-size: 14px;
  line-height: 1.3;
}

/* ── 普通错误（回退） ── */
.bubble-error {
  font-size: 13px;
  color: #b91c1c;
  padding: 4px 0;
}
</style>
