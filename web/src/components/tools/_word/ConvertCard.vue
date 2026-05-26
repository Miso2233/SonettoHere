<template>
  <div class="word-card convert-card">
    <div class="card-body">
      <span class="convert-icon">📕</span>
      <div>
        <div class="card-title">{{ titleText }}</div>
        <div class="card-filename" v-if="data.filename">
          📄 {{ data.filename }} → <span class="pdf-label">.pdf</span>
        </div>
        <div class="card-output" v-if="data.output_filename">
          📕 {{ data.output_filename }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ data: Record<string, any> }>()

const titleText = computed(() => {
  return props.data.success !== false ? '转换成功' : '转换失败'
})
</script>

<style scoped>
.word-card { padding: 12px 4px; }
.card-body {
  display: flex;
  align-items: center;
  gap: 12px;
}
.convert-icon { font-size: 26px; }
.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #dc2626;
}
.card-filename {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}
.pdf-label {
  font-weight: 700;
  color: #dc2626;
}
.card-output {
  font-size: 12px;
  color: var(--text-primary);
  background: var(--bg-secondary);
  padding: 3px 8px;
  border-radius: 4px;
  margin-top: 4px;
  display: inline-block;
  font-family: 'SF Mono', 'Consolas', monospace;
}
</style>
