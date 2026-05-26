<template>
  <div class="word-card table-card">
    <div class="card-header">
      <span class="table-icon">📊</span>
      <div>
        <div class="card-title">{{ titleText }}</div>
        <div class="card-filename" v-if="data.filename">📄 {{ data.filename }}</div>
      </div>
    </div>

    <!-- 添加表格信息 -->
    <div class="table-dimensions" v-if="data.rows && data.cols">
      <span class="dim-badge">{{ data.rows }} 行</span>
      <span class="dim-sep">×</span>
      <span class="dim-badge">{{ data.cols }} 列</span>
    </div>

    <!-- 表格参数摘要 -->
    <div class="params" v-if="paramLines.length">
      <div class="param-row" v-for="(p, i) in paramLines" :key="i">
        <span class="param-key">{{ p.key }}</span>
        <span class="param-val">{{ p.val }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ data: Record<string, any> }>()

const titleText = computed(() => {
  const a = props.data.action
  if (a === 'add_table') return '添加表格'
  return (a?.replace(/^table_/, '')?.replace(/_/g, ' ') || '表格操作').replace(/^\w/, c => c.toUpperCase())
})

const PARAM_LABELS: Record<string, string> = {
  column_width: '列宽',
  width: '宽度',
  alignment: '对齐',
  shading: '底色',
  cell_alignment: '单元格对齐',
  text_align: '文本对齐',
  padding: '边距',
  rows: '行数',
  cols: '列数',
}

const paramLines = computed(() => {
  const lines: { key: string; val: string }[] = []
  for (const [k, v] of Object.entries(props.data)) {
    if (['tool_type', 'action', 'success', 'message', 'filename', 'rows', 'cols'].includes(k)) continue
    if (v !== null && v !== undefined && v !== '' && typeof v !== 'object') {
      const label = PARAM_LABELS[k] || k.replace(/_/g, ' ')
      lines.push({ key: label, val: String(v) })
    }
  }
  return lines.slice(0, 6)
})
</script>

<style scoped>
.word-card { padding: 12px 4px; }
.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.table-icon { font-size: 22px; line-height: 1; }
.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #6d28d9;
}
.card-filename {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}
.table-dimensions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.dim-badge {
  background: #ede9fe;
  color: #6d28d9;
  padding: 4px 12px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
}
.dim-sep {
  color: var(--text-secondary);
  font-size: 16px;
}
.params {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
}
.param-row {
  display: flex;
  gap: 4px;
  font-size: 12px;
}
.param-key { color: var(--text-secondary); }
.param-val { color: var(--text-primary); font-weight: 500; }
</style>
