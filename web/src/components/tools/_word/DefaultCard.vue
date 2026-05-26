<template>
  <div class="word-card default-card">
    <!-- 成功批示 -->
    <div class="succ-line" v-if="data.success !== false">
      <span class="succ-icon">✓</span>
      <span>操作完成</span>
    </div>
    <div class="err-line" v-else>
      <span class="err-icon">✗</span>
      <span>操作失败</span>
    </div>

    <!-- 文件名 -->
    <div class="file-name" v-if="data.filename">📄 {{ data.filename }}</div>

    <!-- 消息摘要 -->
    <div class="msg-text" v-if="data.message">{{ data.message }}</div>

    <!-- 原始输出（折叠） -->
    <div class="raw-section" v-if="rawOutput">
      <div class="raw-toggle" @click="showRaw = !showRaw">
        {{ showRaw ? '收起原始输出' : '查看原始输出' }}
      </div>
      <pre class="raw-code" v-if="showRaw">{{ rawOutput }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<{ data: Record<string, any>; rawOutput: string | null }>()

const showRaw = ref(false)
</script>

<style scoped>
.word-card { padding: 12px 4px; }
.succ-line, .err-line {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 6px;
}
.succ-line { color: #16a34a; }
.err-line { color: #b91c1c; }
.succ-icon, .err-icon {
  width: 20px; height: 20px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px;
}
.succ-icon { background: #dcfce7; }
.err-icon { background: #fee2e2; }

.file-name {
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  padding: 3px 8px;
  border-radius: 4px;
  display: inline-block;
  margin-bottom: 6px;
}
.msg-text {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.5;
}
.raw-section { margin-top: 8px; }
.raw-toggle {
  font-size: 11px;
  color: var(--accent);
  cursor: pointer;
  user-select: none;
  padding: 4px 0;
}
.raw-toggle:hover { opacity: 0.8; }
.raw-code {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 11px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--bg-primary);
  padding: 8px 10px;
  border-radius: 6px;
  max-height: 150px;
  overflow-y: auto;
  margin: 4px 0 0;
}
</style>
