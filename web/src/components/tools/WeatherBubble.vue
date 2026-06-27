<template>
  <BubbleChrome :tool-call="toolCall">
    <!-- 运行中 -->
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>正在查询天气...</span>
    </div>

    <!-- 错误 -->
    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '查询失败' }}
    </div>

    <!-- 完成 -->
    <template v-else-if="toolCall.status === 'done'">
      <div v-if="hasData" class="weather-result">
        <!-- 主卡片：极简线框风 -->
        <div class="card-lineframe">
          <!-- 头部 -->
          <div class="lf-header">
            <div class="lf-header-left">
              <div class="lf-city">{{ cityName }}</div>
              <div class="lf-time" v-if="td.update_time">{{ td.update_time }}</div>
            </div>
            <div class="lf-header-icon" v-html="svgIcon(conditionText, 36)"></div>
          </div>

          <!-- 温度 -->
          <div class="lf-temp-row">
            <span class="lf-temp">{{ tempValue }}</span>
            <span class="lf-unit">{{ tempUnit || '°C' }}</span>
          </div>

          <!-- 天气状况 -->
          <div class="lf-cond-row">
            <span class="lf-cond-icon" v-html="svgIcon(conditionText, 18)"></span>
            <span>{{ conditionText }}</span>
            <span class="divider">|</span>
            <span>{{ windText }}</span>
            <span class="divider" v-if="td.humidity">|</span>
            <span v-if="td.humidity">湿度 {{ td.humidity }}</span>
          </div>

          <!-- 天气预警 -->
          <div class="lf-alerts" v-if="td.alerts && td.alerts.length">
            <div v-for="(alert, i) in td.alerts" :key="i" class="lf-alert-item"
                 :class="'alert-level-' + (alert.level || 'unknown')">
              <div class="alert-header">
                <span class="alert-icon">&#9888;</span>
                <span class="alert-title">{{ alert.title }}</span>
                <span class="alert-level-tag">{{ alert.level }}</span>
              </div>
              <div class="alert-text">{{ alert.text }}</div>
              <div class="alert-footer" v-if="alert.guidance && alert.guidance.length">
                <div v-for="(g, gi) in (Array.isArray(alert.guidance) ? alert.guidance : [alert.guidance])"
                     :key="gi" class="alert-guidance">· {{ g }}</div>
              </div>
            </div>
          </div>

          <!-- 详情 -->
          <div class="lf-details" v-if="hasDetails">
            <div class="lf-detail-item" v-if="td.temp_feel">
              体感<span class="lf-dv">{{ td.temp_feel }}</span>
            </div>
            <div class="lf-detail-item" v-if="td.visibility">
              能见度<span class="lf-dv">{{ td.visibility }}</span>
            </div>
            <div class="lf-detail-item" v-if="td.pressure">
              气压<span class="lf-dv">{{ td.pressure }}</span>
            </div>
            <div class="lf-detail-item" v-if="td.cloud">
              云量<span class="lf-dv">{{ td.cloud }}</span>
            </div>
            <div class="lf-detail-item" v-if="td.aqi !== undefined && td.aqi !== null">
              AQI<span class="lf-dv">{{ td.aqi }}<span class="aqi-label" v-if="td.aqi_category">{{ td.aqi_category }}</span></span>
            </div>
            <div class="lf-detail-item" v-if="td.uv !== undefined && td.uv !== null">
              UV<span class="lf-dv">{{ td.uv }}</span>
            </div>
          </div>

          <!-- 预报 -->
          <div class="lf-forecast" v-if="forecastList.length">
            <div v-for="(day, i) in forecastList" :key="i" class="lf-fc-day">
              <div class="day">{{ formatDay(day.day) }}</div>
              <div class="fc-icon" v-html="svgIcon(day.condition, 20)"></div>
              <div class="hi">{{ day.high }}</div>
              <div class="lo">{{ day.low }}</div>
              <div class="fc-cond">{{ day.condition }}</div>
              <div class="fc-meta" v-if="day.pop || day.sunrise || day.sunset || day.humidity">
                <span class="fc-pop" v-if="day.pop">{{ day.pop }}</span>
                <span class="fc-sun" v-if="day.sunrise || day.sunset">
                  {{ day.sunrise || '' }}<template v-if="day.sunrise && day.sunset">/</template>{{ day.sunset || '' }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 降级 -->
      <div v-else class="raw-output">{{ displayOutput }}</div>
    </template>
  </BubbleChrome>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ToolCall } from '@/types'
import type { WeatherData, WeatherForecastItem } from './weather-types'
import BubbleChrome from './_shared/BubbleChrome.vue'

const props = defineProps<{ toolCall: ToolCall }>()
defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

const rawOutput = props.toolCall.output
if (rawOutput) {
  try {
    const parsed = JSON.parse(rawOutput)
    console.log('[WeatherBubble] raw output data keys:', Object.keys(parsed.data || {}), 'forecast:', JSON.stringify(parsed.data?.forecast?.slice(0, 2)))
  } catch {}
}

// ── 数据源 ──
const td = computed<WeatherData>(() => {
  if (props.toolCall.toolData) return props.toolCall.toolData as WeatherData
  if (props.toolCall.output) {
    try {
      const p = JSON.parse(props.toolCall.output)
      if (p?.data) return p.data as WeatherData
    } catch { /* ignore */ }
  }
  return {}
})

const hasData = computed(() => Object.keys(td.value).length > 0)

// ── 核心字段 ──
const cityName = computed(() => td.value.city || '未知城市')
const conditionText = computed(() => td.value.condition || '')
const windText = computed(() => td.value.wind || '')

// ── 温度解析 ──
const tempValue = computed(() => {
  const raw = String(td.value.temp || '')
  return raw.replace(/°[CF]?$/, '') || raw
})
const tempUnit = computed(() => {
  const raw = String(td.value.temp || '')
  if (raw.includes('°F')) return '°F'
  return '°C'
})

// ── SVG 天气图标工厂 ──

function svgSunny(size: number): string {
  return `<svg viewBox="0 0 32 32" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="16" cy="16" r="6"/>
    <line x1="16" y1="2" x2="16" y2="6"/>
    <line x1="16" y1="26" x2="16" y2="30"/>
    <line x1="2" y1="16" x2="6" y2="16"/>
    <line x1="26" y1="16" x2="30" y2="16"/>
    <line x1="5.2" y1="5.2" x2="8.2" y2="8.2"/>
    <line x1="23.8" y1="23.8" x2="26.8" y2="26.8"/>
    <line x1="5.2" y1="26.8" x2="8.2" y2="23.8"/>
    <line x1="23.8" y1="8.2" x2="26.8" y2="5.2"/>
  </svg>`
}

function svgCloudy(size: number): string {
  return `<svg viewBox="0 0 32 32" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
    <g opacity="0.7">
      <circle cx="13" cy="11" r="5"/>
      <line x1="13" y1="3" x2="13" y2="4.5" opacity="0.5"/>
      <line x1="13" y1="17.5" x2="13" y2="19" opacity="0.5"/>
      <line x1="5" y1="11" x2="6.5" y2="11" opacity="0.5"/>
      <line x1="19.5" y1="11" x2="21" y2="11" opacity="0.5"/>
      <line x1="6.7" y1="4.7" x2="7.8" y2="5.8" opacity="0.4"/>
      <line x1="18.2" y1="16.2" x2="19.3" y2="17.3" opacity="0.4"/>
    </g>
    <path d="M7 21 Q7 16.5 11 16.5 Q12 13 16 14 Q19 13 20.5 16.5 Q24.5 16 25 21 L7 21Z"/>
  </svg>`
}

function svgOvercast(size: number): string {
  return `<svg viewBox="0 0 32 32" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
    <path d="M5 19 Q5 14 9.5 14 Q10.5 10 15 11 Q19 10 20 14 Q25 13 25.5 19 L5 19Z"/>
    <path d="M7 23 Q7 19 11 19 Q12 16 16 17 Q19.5 16 21 19 Q24.5 18.5 24.5 23 L7 23Z" opacity="0.5"/>
  </svg>`
}

function svgRainy(size: number): string {
  return `<svg viewBox="0 0 32 32" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
    <path d="M5 17 Q5 12 9.5 12 Q10.5 8 15 9 Q19 8 20 12 Q25 11 25.5 17 L5 17Z"/>
    <line x1="9" y1="21" x2="7.5" y2="26"/>
    <line x1="14" y1="21" x2="12.5" y2="27"/>
    <line x1="19" y1="21" x2="17.5" y2="26"/>
    <line x1="24" y1="21" x2="23" y2="25" opacity="0.5"/>
  </svg>`
}

function svgThunder(size: number): string {
  return `<svg viewBox="0 0 32 32" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
    <path d="M5 16 Q5 11 9.5 11 Q10.5 7 15 8 Q19 7 20 11 Q25 10 25.5 16 L5 16Z"/>
    <polyline points="15,16 12,21 15.5,21 13,27" opacity="0.9"/>
    <line x1="8" y1="20" x2="7" y2="23" opacity="0.5"/>
    <line x1="22" y1="20" x2="23" y2="23" opacity="0.5"/>
  </svg>`
}

function svgSnowy(size: number): string {
  return `<svg viewBox="0 0 32 32" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
    <path d="M5 15 Q5 10 9.5 10 Q10.5 6 15 7 Q19 6 20 10 Q25 9 25.5 15 L5 15Z"/>
    <circle cx="9" cy="22" r="1.8" fill="currentColor" stroke="none"/>
    <circle cx="15" cy="24" r="1.8" fill="currentColor" stroke="none"/>
    <circle cx="21" cy="22" r="1.8" fill="currentColor" stroke="none"/>
    <circle cx="12" cy="27" r="1.2" fill="currentColor" stroke="none" opacity="0.6"/>
    <circle cx="18" cy="27" r="1.2" fill="currentColor" stroke="none" opacity="0.6"/>
  </svg>`
}

function svgFoggy(size: number): string {
  return `<svg viewBox="0 0 32 32" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
    <line x1="6" y1="9" x2="26" y2="9" opacity="0.25"/>
    <line x1="8" y1="13" x2="24" y2="13" opacity="0.4"/>
    <line x1="5" y1="17" x2="27" y2="17" opacity="0.55"/>
    <line x1="7" y1="21" x2="25" y2="21" opacity="0.4"/>
    <line x1="10" y1="25" x2="22" y2="25" opacity="0.25"/>
  </svg>`
}

function svgWindy(size: number): string {
  return `<svg viewBox="0 0 32 32" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
    <path d="M4 11 Q10 6 16 8 Q19 9 21 7.5" opacity="0.8"/>
    <path d="M3 16 Q9 12 16 14 Q22 16 26 12.5" opacity="0.6"/>
    <path d="M4 21 Q11 17.5 18 19.5 Q23 21 27 18" opacity="0.45"/>
    <path d="M8 26 Q14 23 20 25" opacity="0.3"/>
  </svg>`
}

// ── 根据条件文字选择 SVG 图标 ──
function svgIcon(condition: string, size: number): string {
  const c = (condition || '').toLowerCase()
  if (c.includes('雷') || c.includes('暴')) return svgThunder(size)
  if (c.includes('雪')) return svgSnowy(size)
  if (c.includes('雨')) return svgRainy(size)
  if (c.includes('雾') || c.includes('霾')) return svgFoggy(size)
  if (c.includes('晴') && (c.includes('云') || c.includes('间'))) {
    return svgCloudy(size)
  }
  if (c.includes('晴')) return svgSunny(size)
  if (c.includes('多云')) return svgCloudy(size)
  if (c.includes('阴') || c.includes('云')) return svgOvercast(size)
  if (c.includes('风')) return svgWindy(size)
  return svgSunny(size)
}

// ── 详情 ──
const hasDetails = computed(() =>
  !!(td.value.temp_feel || td.value.visibility || td.value.pressure || td.value.cloud
     || td.value.aqi != null || td.value.uv != null)
)

// ── 预报 ──
const forecastList = computed<WeatherForecastItem[]>(() => {
  const fc = td.value.forecast
  return Array.isArray(fc) ? fc : []
})

function formatDay(day: string): string {
  if (!day) return ''
  // "2026-05-16" → "5/16"
  const m = day.match(/^\d{4}-(\d{2})-(\d{2})$/)
  if (m) return `${parseInt(m[1])}/${parseInt(m[2])}`
  return day
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

.bubble-error {
  font-size: 13px;
  color: #b91c1c;
  padding: 4px 0;
}

/* ── 极简线框风卡片 ── */
.weather-result {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 4px 0;
}

.card-lineframe {
  border: 1px solid var(--border);
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  background: var(--bg-primary);
  border-radius: 2px;
}

/* ── 头部 ── */
.lf-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.lf-header-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.lf-city {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--text-secondary);
}
.lf-time {
  font-size: 10px;
  color: var(--text-tertiary, #bbb);
  letter-spacing: 0.3px;
}
.lf-header-icon {
  width: 36px;
  height: 36px;
  color: var(--text-primary);
  flex-shrink: 0;
}
.lf-header-icon svg {
  width: 100%;
  height: 100%;
}

/* ── 温度 ── */
.lf-temp-row {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.lf-temp {
  font-size: 52px;
  font-weight: 200;
  line-height: 1;
  letter-spacing: -2px;
  color: var(--text-primary);
}
.lf-unit {
  font-size: 20px;
  font-weight: 300;
  color: var(--text-secondary);
}

/* ── 天气状况行 ── */
.lf-cond-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}
.lf-cond-row .divider {
  color: var(--text-tertiary, #ddd);
  font-weight: 300;
}
.lf-cond-icon {
  width: 18px;
  height: 18px;
  color: var(--text-secondary);
  display: inline-flex;
}
.lf-cond-icon svg {
  width: 100%;
  height: 100%;
}

/* ── 详情 ── */
.lf-details {
  display: flex;
  gap: 0;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  padding: 10px 0;
}
.lf-detail-item {
  flex: 1;
  text-align: center;
  font-size: 10px;
  color: var(--text-secondary);
  letter-spacing: 0.3px;
  text-transform: uppercase;
  border-right: 1px solid var(--border);
}
.lf-detail-item:last-child {
  border-right: none;
}
.lf-dv {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-top: 3px;
}
.aqi-label {
  display: inline-block;
  font-size: 9px;
  font-weight: 400;
  color: var(--text-tertiary);
  margin-left: 2px;
}

/* ── 预报 ── */
.lf-forecast {
  display: flex;
  gap: 4px;
}
.lf-fc-day {
  flex: 1;
  text-align: center;
  padding: 8px 4px;
  border: 1px solid var(--border);
  min-width: 0;
}
.lf-fc-day .day {
  font-size: 10px;
  color: var(--text-secondary);
}
.lf-fc-day .fc-icon {
  width: 20px;
  height: 20px;
  color: var(--text-secondary);
  margin: 4px auto;
}
.lf-fc-day .fc-icon svg {
  width: 100%;
  height: 100%;
}
.lf-fc-day .hi {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.lf-fc-day .lo {
  font-size: 11px;
  color: var(--text-secondary);
}
.lf-fc-day .fc-cond {
  font-size: 10px;
  color: var(--text-secondary);
  margin-top: 2px;
}
.fc-meta {
  font-size: 9px;
  color: var(--text-tertiary);
  margin-top: 4px;
  line-height: 1.4;
}
.fc-pop, .fc-sun {
  display: block;
}

/* ── 预警 ── */
.lf-alerts {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.lf-alert-item {
  padding: 10px 12px;
  border-left: 3px solid;
  font-size: 12px;
  line-height: 1.5;
  background: var(--bg-primary);
}
.lf-alert-item.alert-level-red { border-color: #dc2626; background: rgba(220,38,38,0.04); }
.lf-alert-item.alert-level-orange { border-color: #ea580c; background: rgba(234,88,12,0.04); }
.lf-alert-item.alert-level-yellow { border-color: #ca8a04; background: rgba(202,138,4,0.04); }
.lf-alert-item.alert-level-blue { border-color: #2563eb; background: rgba(37,99,235,0.04); }
.lf-alert-item.alert-level-unknown { border-color: var(--border); }
.alert-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}
.alert-icon { font-size: 14px; }
.alert-title { font-weight: 600; color: var(--text-primary); }
.alert-level-tag {
  margin-left: auto;
  font-size: 10px;
  padding: 1px 6px;
  border: 1px solid var(--border);
  text-transform: uppercase;
}
.alert-text { color: var(--text-secondary); font-size: 11px; margin-top: 4px; }
.alert-footer { margin-top: 6px; }
.alert-guidance { font-size: 11px; color: var(--text-tertiary); line-height: 1.6; }

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
