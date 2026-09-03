<template>
  <BubbleChrome :tool-call="toolCall">
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>正在查看后台任务...</span>
    </div>

    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '查看后台任务失败' }}
    </div>

    <template v-else-if="toolCall.status === 'done'">
      <div v-if="hasData" class="bl">
        <div class="bl-bar">
          <span class="bl-title">后台任务</span>
          <span class="bl-stats">{{ total }} 项 · 运行中 {{ running }}</span>
        </div>

        <div v-if="tasks.length" class="bl-list">
          <div v-for="t in tasks" :key="t.index" class="bl-item">
            <div class="bl-item-head">
              <span class="bl-index">#{{ t.index }}</span>
              <span class="bl-tool">{{ toolDisplayName(t.tool_name) }}</span>
              <span class="bl-tag" :class="t.status">{{ statusLabel(t.status) }}</span>
              <span class="bl-elapsed">{{ t.elapsed_s }}s</span>
            </div>
            <div v-if="argsText(t)" class="bl-args">{{ argsText(t) }}</div>
          </div>
        </div>

        <div v-else class="bl-empty">无后台任务</div>
      </div>

      <div v-else class="bl-raw">{{ fallback }}</div>
    </template>
  </BubbleChrome>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ToolCall } from '@/types'
import BubbleChrome from './_shared/BubbleChrome.vue'
import { toolDisplayName } from './_shared/displayNames'

const props = defineProps<{ toolCall: ToolCall }>()

interface BgTaskRow {
  index: number
  tool_name: string
  args_summary: string
  status: string
  elapsed_s: number
}

const td = computed<Record<string, unknown>>(() => {
  if (props.toolCall.toolData) return props.toolCall.toolData
  if (props.toolCall.output) {
    try {
      const p = JSON.parse(props.toolCall.output) as { data?: Record<string, unknown> }
      if (p?.data) return p.data
    } catch { /* */ }
  }
  return {}
})

const hasData = computed(() => Object.keys(td.value).length > 0)
const total = computed(() => Number(td.value['total'] ?? 0))
const running = computed(() => Number(td.value['running'] ?? 0))
const tasks = computed<BgTaskRow[]>(() => {
  const raw = td.value['tasks']
  return Array.isArray(raw) ? (raw as BgTaskRow[]) : []
})

function statusLabel(status: string): string {
  if (status === 'running') return '运行中'
  if (status === 'completed') return '已完成'
  if (status === 'failed') return '失败'
  return status
}

function argsText(t: BgTaskRow): string {
  const oneLine = (t.args_summary ?? '').replace(/\s+/g, ' ').trim()
  return oneLine.length > 100 ? oneLine.slice(0, 100) + '…' : oneLine
}

const fallback = computed(() =>
  props.toolCall.output
    ? (props.toolCall.output.length > 500 ? props.toolCall.output.slice(0, 500) + '…' : props.toolCall.output)
    : null
)
</script>

<style scoped>
/* ── 布局常量（与 Tavily 系列一致：黑白撞色 + 灰阶） ── */
.bubble-running {
  padding: 12px 0;
  font-size: 13px;
  color: #888;
}
.bubble-error {
  padding: 8px 0;
  font-size: 13px;
  color: #666;
}

.bl {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 4px 0;
}

/* ── 顶栏（同 tavily 查询栏） ── */
.bl-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #f5f5f5;
  border-radius: 6px;
}
.bl-title {
  font-size: 14px;
  font-weight: 600;
  color: #000;
}
.bl-stats {
  margin-left: auto;
  font-size: 11px;
  color: #888;
  white-space: nowrap;
  flex-shrink: 0;
}

/* ── 任务列表（同 tavily 结果项） ── */
.bl-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.bl-item {
  padding: 10px 12px;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  transition: border-color .15s;
}
.bl-item:hover { border-color: #000; }

.bl-item-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.bl-index {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 11px;
  font-weight: 700;
  color: #000;
  flex-shrink: 0;
}
.bl-tool {
  font-size: 13px;
  font-weight: 600;
  color: #000;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bl-elapsed {
  font-size: 11px;
  color: #999;
  flex-shrink: 0;
}

/* ── 状态标签：黑白撞色 ── */
.bl-tag {
  font-size: 10px;
  padding: 1px 8px;
  border-radius: 2px;
  font-weight: 600;
  flex-shrink: 0;
}
.bl-tag.running {
  background: #000;
  color: #fff;
}
.bl-tag.completed {
  border: 1px solid #ccc;
  color: #555;
}
.bl-tag.failed {
  border: 1px solid #b91c1c;
  color: #b91c1c;
}

.bl-args {
  font-size: 12px;
  color: #888;
  margin: 4px 0 0;
  font-family: 'SF Mono', 'Consolas', monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── 空态 / 降级 ── */
.bl-empty {
  text-align: center;
  padding: 28px 16px;
  color: #999;
  font-size: 13px;
}
.bl-raw {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  color: #333;
  white-space: pre-wrap;
  word-break: break-word;
  padding: 8px 12px;
  background: #fafafa;
  border-radius: 4px;
}
</style>
