<template>
  <BubbleChrome :tool-call="toolCall">
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>{{ isDateMode ? '查询节日...' : '查询日历...' }}</span>
    </div>

    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '查询失败' }}
    </div>

    <template v-else-if="toolCall.status === 'done'">
      <div v-if="hasData" class="hb">
        <!-- 顶栏：日期/时段 + 统计（同 tavily 查询栏） -->
        <div class="hb-bar">
          <span class="hb-title">{{ titleText }}</span>
          <span class="hb-stats">{{ statsText }}</span>
        </div>

        <!-- 日期模式：大日期行 -->
        <div v-if="isDateMode" class="hb-hero">
          <span class="hb-day-num">{{ dateDay }}</span>
          <div class="hb-day-info">
            <div class="hb-weekday">{{ dateWeekday }}</div>
            <div v-if="lunarLine" class="hb-day-sub">{{ lunarLine }}</div>
          </div>
          <span v-if="dayTone" class="hb-day-tag" :class="dayTone">{{ dayLabel }}</span>
        </div>

        <!-- 节日列表（同 tavily 结果项） -->
        <div v-if="holidayItems.length" class="hb-list">
          <div v-for="(item, i) in holidayItems" :key="i" class="hb-item">
            <span class="hb-rank">{{ i + 1 }}</span>
            <div class="hb-item-body">
              <div class="hb-item-head">
                <span class="hb-name">{{ item.name }}</span>
                <span class="hb-tag" :class="{ strong: isLegal(item.type) }">{{ typeLabel(item.type) }}</span>
                <span v-if="item.is_workday" class="hb-tag">调休上班</span>
              </div>
              <div v-if="item.date" class="hb-item-date">{{ item.date }}</div>
            </div>
          </div>
        </div>
        <div v-else-if="!isDateMode" class="hb-empty">该时段暂无节日</div>

        <!-- 当日干支/节气（灰色信息行） -->
        <div v-if="ganzhiLine" class="hb-meta-row">
          <span class="hb-meta-label">干支</span>
          <span class="hb-meta-value">{{ ganzhiLine }}</span>
        </div>

        <!-- 附近节日 -->
        <div v-if="nearbyPrev.length || nearbyNext.length" class="hb-nearby">
          <div v-if="nearbyPrev.length" class="hb-nearby-group">
            <div class="hb-nearby-label">← 之前</div>
            <div v-for="(nb, i) in nearbyPrev" :key="'p' + i" class="hb-nearby-item">
              <span class="hb-nb-date">{{ nb.date }}</span>
              <span class="hb-nb-events">{{ nb.eventNames }}</span>
            </div>
          </div>
          <div v-if="nearbyNext.length" class="hb-nearby-group">
            <div class="hb-nearby-label">之后 →</div>
            <div v-for="(nb, i) in nearbyNext" :key="'n' + i" class="hb-nearby-item">
              <span class="hb-nb-date">{{ nb.date }}</span>
              <span class="hb-nb-events">{{ nb.eventNames }}</span>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="hb-raw">{{ fallback }}</div>
    </template>
  </BubbleChrome>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ToolCall } from '@/types'
import BubbleChrome from './_shared/BubbleChrome.vue'

const props = defineProps<{ toolCall: ToolCall }>()

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

const hasData = computed(() => Object.keys(td.value).length > 0)

// ── 查询模式 ──
const isDateMode = computed(() => td.value.mode === 'day')

const rawDate = computed(() => td.value.date || '')

const titleText = computed(() => {
  if (isDateMode.value) return rawDate.value || '日历'
  if (td.value.month) return String(td.value.month)
  if (td.value.year) return `${td.value.year}年`
  return '日历'
})

const statsText = computed(() => {
  if (isDateMode.value) {
    const parts: string[] = []
    if (td.value.weekday) parts.push(String(td.value.weekday))
    if (td.value.solar_term) parts.push(String(td.value.solar_term))
    return parts.join(' · ')
  }
  const parts: string[] = []
  if (td.value.total_days) parts.push(`共 ${td.value.total_days} 天`)
  if (td.value.rest_days) parts.push(`休息 ${td.value.rest_days} 天`)
  if (td.value.workdays) parts.push(`工作 ${td.value.workdays} 天`)
  if (td.value.holiday_events) parts.push(`${td.value.holiday_events} 个节日`)
  return parts.join(' · ')
})

// ── 日期模式主行 ──
const dateDay = computed(() => {
  const d = rawDate.value
  const parts = d.split('-')
  return parts.length >= 3 ? parts[2] : d
})
const dateWeekday = computed(() => td.value.weekday || '')

const firstDay = computed<Record<string, any> | null>(() => {
  const days = td.value.days
  return Array.isArray(days) && days.length > 0 ? days[0] : null
})

const lunarLine = computed(() => {
  const first = firstDay.value
  if (!first) return td.value.lunar_date || ''
  const lunar = first.lunar_date || `${first.lunar_month ?? ''}${first.lunar_day ?? ''}`.trim()
  return lunar || ''
})

const ganzhiLine = computed(() => {
  const first = firstDay.value
  if (!first?.ganzhi_year) return ''
  const parts = [`${first.ganzhi_year}年`]
  if (first.ganzhi_month) parts.push(`${first.ganzhi_month}月`)
  if (first.ganzhi_day) parts.push(`${first.ganzhi_day}日`)
  return parts.join(' ')
})

// ── 当日休息/工作标记（黑白撞色：休息=黑底白字，调休上班=黑边框） ──
const dayTone = computed((): 'rest' | 'work' | '' => {
  const first = firstDay.value
  if (!first) return ''
  if (first.is_rest_day) return 'rest'
  if (first.is_holiday === false && (first.ganzhi_year || td.value.weekday)) return 'work'
  return ''
})

const dayLabel = computed(() => (dayTone.value === 'rest' ? '休息日' : '工作日'))

// ── 节日事件列表 ──
const holidayItems = computed<Array<Record<string, any>>>(() => {
  const items = td.value.holidays
  return Array.isArray(items) ? items : []
})

// ── 附近节日 ──
const nearbyPrev = computed<Array<{ date: string; eventNames: string }>>(() => {
  const nb = td.value.nearby
  if (!nb || typeof nb !== 'object') return []
  const prev = Array.isArray(nb.previous) ? nb.previous : []
  return prev.map((item: any) => ({
    date: item.date || '',
    eventNames: (item.events || []).map((e: any) => e.name).join('、'),
  }))
})

const nearbyNext = computed<Array<{ date: string; eventNames: string }>>(() => {
  const nb = td.value.nearby
  if (!nb || typeof nb !== 'object') return []
  const next = Array.isArray(nb.next) ? nb.next : []
  return next.map((item: any) => ({
    date: item.date || '',
    eventNames: (item.events || []).map((e: any) => e.name).join('、'),
  }))
})

function typeLabel(type: string): string {
  switch (type) {
    case 'legal_rest': return '法定假日'
    case 'legal_workday_adjust': return '调休上班'
    case 'legal': return '法定'
    case 'solar': return '公历'
    case 'lunar': return '农历'
    case 'term': return '节气'
    default: return '节日'
  }
}

function isLegal(type: string): boolean {
  return typeof type === 'string' && type.startsWith('legal')
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

.hb {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 4px 0;
}

/* ── 顶栏（同 tavily 查询栏） ── */
.hb-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #f5f5f5;
  border-radius: 6px;
  flex-wrap: wrap;
}
.hb-title {
  font-size: 14px;
  font-weight: 600;
  color: #000;
  font-variant-numeric: tabular-nums;
}
.hb-stats {
  margin-left: auto;
  font-size: 11px;
  color: #888;
  white-space: nowrap;
  flex-shrink: 0;
}

/* ── 日期模式 hero 行 ── */
.hb-hero {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 4px 2px;
}
.hb-day-num {
  font-size: 40px;
  font-weight: 700;
  line-height: 1;
  color: #000;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}
.hb-day-info {
  flex: 1;
  min-width: 0;
}
.hb-weekday {
  font-size: 15px;
  font-weight: 600;
  color: #000;
}
.hb-day-sub {
  font-size: 12px;
  color: #888;
  margin-top: 2px;
}
.hb-day-tag {
  font-size: 10px;
  padding: 1px 8px;
  border-radius: 2px;
  font-weight: 600;
  flex-shrink: 0;
}
.hb-day-tag.rest {
  background: #000;
  color: #fff;
}
.hb-day-tag.work {
  border: 1px solid #ccc;
  color: #555;
}

/* ── 节日列表（同 tavily 结果项） ── */
.hb-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.hb-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  transition: border-color .15s;
}
.hb-item:hover { border-color: #000; }

.hb-rank {
  font-size: 11px;
  font-weight: 700;
  color: #000;
  flex-shrink: 0;
  min-width: 18px;
  text-align: center;
  margin-top: 2px;
}
.hb-item-body {
  flex: 1;
  min-width: 0;
}
.hb-item-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.hb-name {
  font-size: 14px;
  font-weight: 600;
  color: #000;
  line-height: 1.4;
}
.hb-tag {
  font-size: 10px;
  padding: 1px 6px;
  border: 1px solid #ccc;
  border-radius: 2px;
  color: #555;
  font-weight: 600;
}
.hb-item-date {
  font-size: 11px;
  color: #888;
  margin-top: 2px;
}

/* ── 当日干支（灰色信息行） ── */
.hb-meta-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  font-size: 12px;
  padding: 6px 12px;
  background: #fafafa;
  border-radius: 4px;
}
.hb-meta-row .hb-meta-label {
  color: #999;
  font-weight: 600;
  flex-shrink: 0;
}
.hb-meta-value {
  color: #333;
  font-family: 'SF Mono', 'Consolas', monospace;
}

/* ── 附近节日 ── */
.hb-nearby-group + .hb-nearby-group {
  margin-top: 8px;
}
.hb-nearby-label {
  font-size: 11px;
  font-weight: 600;
  color: #999;
  margin-bottom: 4px;
}
.hb-nearby-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 3px 2px;
  font-size: 13px;
}
.hb-nb-date {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 11px;
  font-weight: 700;
  color: #000;
  white-space: nowrap;
}
.hb-nb-events {
  color: #444;
}

/* ── 空态 / 降级 ── */
.hb-empty {
  text-align: center;
  padding: 28px 16px;
  color: #999;
  font-size: 13px;
}
.hb-raw {
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
