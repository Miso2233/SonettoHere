<template>
  <BubbleChrome :tool-call="toolCall">
    <!-- 运行中 -->
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>{{ isDateMode ? '查询节日...' : '查询日历...' }}</span>
    </div>

    <!-- 错误 -->
    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '查询失败' }}
    </div>

    <!-- 完成 -->
    <template v-else-if="toolCall.status === 'done'">
      <div v-if="hasData" class="holiday-result">

        <!-- ===== 日期模式：当日 + 附近节日 ===== -->
        <template v-if="isDateMode">
          <!-- 主日期卡片 -->
          <div class="holiday-hero">
            <div class="hero-date">
              <span class="hero-month">{{ dateMonth }}</span>
              <span class="hero-day">{{ dateDay }}</span>
            </div>
            <div class="hero-info">
              <div class="hero-weekday">{{ dateWeekday }}</div>
              <div class="hero-lunar" v-if="td.lunar_date">{{ td.lunar_date }}</div>
              <div class="hero-term" v-if="td.solar_term">{{ td.solar_term }}</div>
            </div>
          </div>

          <!-- 节日事件列表 -->
          <div v-if="holidayItems.length" class="holiday-items">
            <div v-for="(item, i) in holidayItems" :key="i" class="holiday-item" :class="'type-' + typeClass(item.type)">
              <div class="hi-body">
                <div class="hi-name">{{ item.name }}</div>
                <div class="hi-meta">
                  <span class="hi-type" :class="'type-' + typeClass(item.type)">{{ typeLabel(item.type) }}</span>
                  <span v-if="item.date" class="hi-date">{{ item.date }}</span>
                  <span v-if="item.is_workday" class="hi-badge badge-workday">调休上班</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 日期详情（干支、节气等信息） -->
          <div v-if="firstDay && (firstDay.ganzhi_year || firstDay.solar_term || firstDay.solar_festival || firstDay.lunar_festival)" class="holiday-day-detail">
            <div class="detail-title">当日详情</div>
            <div class="detail-grid">
              <div v-if="firstDay.solar_festival" class="detail-cell">
                <span class="dc-label">公历节日</span>
                <span class="dc-value">{{ firstDay.solar_festival }}</span>
              </div>
              <div v-if="firstDay.lunar_festival" class="detail-cell">
                <span class="dc-label">农历节日</span>
                <span class="dc-value">{{ firstDay.lunar_festival }}</span>
              </div>
              <div v-if="firstDay.solar_term" class="detail-cell">
                <span class="dc-label">节气</span>
                <span class="dc-value">{{ firstDay.solar_term }}</span>
              </div>
              <div v-if="firstDay.ganzhi_year" class="detail-cell">
                <span class="dc-label">干支</span>
                <span class="dc-value">{{ firstDay.ganzhi_year }}年 {{ firstDay.ganzhi_month }}月 {{ firstDay.ganzhi_day }}日</span>
              </div>
            </div>
          </div>

          <!-- 附近节日 -->
          <div v-if="nearbyPrev.length || nearbyNext.length" class="holiday-nearby">
            <div class="nearby-title">附近节日</div>
            <div v-if="nearbyPrev.length" class="nearby-group">
              <div class="nearby-direction">⬅ 之前</div>
              <div class="nearby-list">
                <div v-for="(nb, i) in nearbyPrev" :key="'p'+i" class="nearby-item">
                  <span class="nb-date">{{ nb.date }}</span>
                  <span class="nb-events">{{ nb.eventNames }}</span>
                </div>
              </div>
            </div>
            <div v-if="nearbyNext.length" class="nearby-group">
              <div class="nearby-direction">之后 ➡</div>
              <div class="nearby-list">
                <div v-for="(nb, i) in nearbyNext" :key="'n'+i" class="nearby-item">
                  <span class="nb-date">{{ nb.date }}</span>
                  <span class="nb-events">{{ nb.eventNames }}</span>
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- ===== 月/年模式：节日列表 ===== -->
        <template v-else>
          <div class="holiday-period-header">
            <span class="period-icon">📆</span>
            <span class="period-title">{{ periodTitle }}</span>
          </div>
          <div v-if="td.total_days" class="period-summary">
            <span class="ps-item">共 {{ td.total_days }} 天</span>
            <span v-if="td.rest_days" class="ps-item">休息 {{ td.rest_days }} 天</span>
            <span v-if="td.workdays" class="ps-item">工作 {{ td.workdays }} 天</span>
            <span v-if="td.holiday_events" class="ps-item">{{ td.holiday_events }} 个节日</span>
          </div>
          <div v-if="holidayItems.length" class="holiday-items">
            <div v-for="(item, i) in holidayItems" :key="i" class="holiday-item" :class="'type-' + typeClass(item.type)">
              <div class="hi-body">
                <div class="hi-name">{{ item.name }}</div>
                <div class="hi-meta">
                  <span class="hi-type" :class="'type-' + typeClass(item.type)">{{ typeLabel(item.type) }}</span>
                  <span v-if="item.date" class="hi-date">{{ item.date }}</span>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="holiday-empty">该时段暂无节日信息</div>
        </template>
      </div>

      <!-- 降级 -->
      <div v-else class="raw-output">{{ displayOutput }}</div>
    </template>
  </BubbleChrome>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ToolCall } from '@/types'
import BubbleChrome from './_shared/BubbleChrome.vue'

const props = defineProps<{ toolCall: ToolCall }>()
const emit = defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

// ── 数据源 ──
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
const periodTitle = computed(() => td.value.month || td.value.year || '日历')

// ── 日期解析 ──
const rawDate = computed(() => td.value.date || '')
const dateMonth = computed(() => {
  const d = rawDate.value
  if (!d) return ''
  const parts = d.split('-')
  return parts.length >= 2 ? `${parts[0]}年${parts[1]}月` : d
})
const dateDay = computed(() => {
  const d = rawDate.value
  if (!d) return ''
  const parts = d.split('-')
  return parts.length >= 3 ? parts[2] : d
})
const dateWeekday = computed(() => td.value.weekday || '')

// ── 取 days[0] 的丰富信息 ──
const firstDay = computed<Record<string, any> | null>(() => {
  const days = td.value.days
  return Array.isArray(days) && days.length > 0 ? days[0] : null
})

// ── 节日事件列表 ──
const holidayItems = computed<Array<Record<string, any>>>(() => {
  const items = td.value.holidays
  return Array.isArray(items) ? items : []
})

// ── 附近节日（结构: {previous: [{date, events:[{name,type,date}]}], next: [...]}） ──
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

// ── 类型工具 ──
function typeClass(type: string): string {
  if (!type) return 'other'
  if (type.startsWith('legal')) return 'legal'
  if (type === 'solar' || type === 'lunar' || type === 'term') return type
  return 'other'
}

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

// ── 降级 ──
const displayOutput = computed(() => {
  if (props.toolCall.output) {
    return props.toolCall.output.length > 500
      ? props.toolCall.output.slice(0, 500) + '...'
      : props.toolCall.output
  }
  return null
})
</script>

<style scoped>
/* ── 运行中 ── */
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

/* ── 主容器 ── */
.holiday-result {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 4px 0;
}

/* ── 日期主卡片 ── */
.holiday-hero {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: linear-gradient(135deg, #d4145a, #fbb03b);
  border-radius: 12px;
  color: #fff;
  box-shadow: 0 2px 12px rgba(0,0,0,0.1);
}

.hero-date {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
}

.hero-month {
  font-size: 13px;
  font-weight: 600;
  opacity: 0.9;
}

.hero-day {
  font-size: 48px;
  font-weight: 700;
  line-height: 1;
  margin-top: 2px;
}

.hero-info {
  flex: 1;
}

.hero-weekday {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 4px;
}

.hero-lunar {
  font-size: 13px;
  opacity: 0.85;
}

.hero-term {
  font-size: 13px;
  opacity: 0.85;
  margin-top: 2px;
}

/* ── 节日列表 ── */
.holiday-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.holiday-item {
  display: flex;
  gap: 12px;
  padding: 10px 12px;
  background: var(--bg-primary);
  border-radius: 8px;
  border: 1px solid var(--border);
  border-left: 3px solid #888;
}

.holiday-item.type-legal { border-left-color: #d4145a; }
.holiday-item.type-solar { border-left-color: #f39c12; }
.holiday-item.type-lunar { border-left-color: #8e44ad; }
.holiday-item.type-term { border-left-color: #27ae60; }

.hi-body {
  flex: 1;
  min-width: 0;
}

.hi-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.4;
}

.hi-meta {
  display: flex;
  gap: 6px;
  margin-top: 4px;
  flex-wrap: wrap;
  align-items: center;
}

.hi-type {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 7px;
  border-radius: 3px;
  letter-spacing: 0.5px;
}

.hi-type.type-legal { background: #fde8e8; color: #c0392b; }
.hi-type.type-solar { background: #fef5e7; color: #d35400; }
.hi-type.type-lunar { background: #f0e8f5; color: #7d3c98; }
.hi-type.type-term { background: #e8f5e9; color: #27ae60; }

.hi-date {
  font-size: 11px;
  color: var(--text-secondary);
}

.hi-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 3px;
}

.badge-workday {
  background: #fff3e0;
  color: #e65100;
}

/* ── 日期详情网格 ── */
.holiday-day-detail {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
  background: var(--bg-primary);
}

.detail-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.detail-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.detail-cell {
  flex: 1;
  min-width: 120px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 10px;
  background: var(--bg-secondary);
  border-radius: 6px;
}

.dc-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.dc-value {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

/* ── 统计摘要 ── */
.period-summary {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.ps-item {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  font-weight: 500;
}

/* ── 附近节日 ── */
.holiday-nearby {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
  background: var(--bg-primary);
}

.nearby-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.nearby-group {
  margin-bottom: 6px;
}

.nearby-group:last-child {
  margin-bottom: 0;
}

.nearby-direction {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.nearby-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nearby-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-primary);
  padding: 3px 6px;
  border-radius: 4px;
  background: var(--bg-secondary);
}

.nb-date {
  font-size: 11px;
  font-weight: 600;
  color: var(--accent);
  white-space: nowrap;
}

.nb-events {
  color: var(--text-primary);
}

/* ── 月/年模式 ── */
.holiday-period-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  padding: 4px 0;
}

.period-icon { font-size: 20px; }

.holiday-empty {
  text-align: center;
  padding: 24px;
  color: var(--text-secondary);
  font-size: 13px;
}

/* ── 降级 ── */
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
