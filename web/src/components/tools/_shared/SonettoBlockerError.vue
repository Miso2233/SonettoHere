<template>
  <!-- SonettoBlocker 阻断错误（特殊视觉：灰底 + 全站最重的黑色边框） -->
  <div v-if="isBlocked" class="blocker-banner">
    <div class="blocker-header">
      <span class="blocker-title">访问已被安全阻断</span>
    </div>
    <div class="blocker-divider" />
    <div class="blocker-body">
      <p class="blocker-intro">此操作因 <strong>SonettoBlocker</strong> 安全机制被阻止：</p>

      <div v-if="blockedPaths.length" class="blocker-section">
        <div class="blocker-label">阻断位置</div>
        <div v-for="(p, i) in blockedPaths" :key="i" class="blocker-path-item">
          <code class="blocker-path-text">{{ p }}</code>
        </div>
      </div>

      <div class="blocker-notice">
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
/* 全灰阶方案：不靠颜色表达「被阻断」，改由平铺灰底 + 全站唯一的 1.5px
   纯黑重边框承担视觉重量。底纹一律平色 —— 斜纹之类的纹理在正文后面会
   明显干扰阅读。 */
.blocker-banner {
  background: color-mix(in srgb, var(--accent) 7%, transparent);
  border: 1.5px solid var(--text-primary);
  border-radius: 10px;
  overflow: hidden;
}

.blocker-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px 6px;
}

.blocker-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.2px;
}

.blocker-divider {
  height: 1px;
  background: var(--border);
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
  color: var(--text-secondary);
  line-height: 1.5;
}

.blocker-intro strong {
  color: var(--text-primary);
  font-weight: 700;
}

.blocker-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* 微大写标签：对齐 Tavily 系列的区块标题规范 */
.blocker-label {
  font-size: 10px;
  font-weight: 700;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* 在斜纹底上「镂空」出来的卡片 */
.blocker-path-item {
  padding: 8px 10px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
}

.blocker-path-text {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  color: var(--text-primary);
  word-break: break-all;
  background: none;
  padding: 0;
}

.blocker-notice {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  padding: 8px 10px;
  background: var(--bg-secondary);
  border-radius: 6px;
}

/* ── 普通错误（回退） ──
   与 Tavily 系列保持一致：正文错误文字走灰阶，而不是全站默认的红。 */
.bubble-error {
  font-size: 13px;
  color: var(--text-secondary);
  padding: 4px 0;
}
</style>
