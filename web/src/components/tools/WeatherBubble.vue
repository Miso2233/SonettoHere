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
        <!-- 主卡片 -->
        <div class="weather-main" :style="{ background: bgGradient }">
          <div class="weather-city">{{ cityName }}</div>
          <div class="weather-temp">{{ tempValue }}<span class="temp-unit">{{ tempUnit }}</span></div>
          <div class="weather-condition">{{ conditionIcon }} {{ conditionText }}</div>
          <div class="weather-wind">{{ windText }}</div>
        </div>

        <!-- 详情 -->
        <div class="weather-details" v-if="hasDetails">
          <div class="detail-item" v-if="td.humidity">
            <span class="detail-label">湿度</span>
            <span class="detail-value">{{ td.humidity }}</span>
          </div>
          <div class="detail-item" v-if="td.temp_feel">
            <span class="detail-label">体感</span>
            <span class="detail-value">{{ td.temp_feel }}</span>
          </div>
          <div class="detail-item" v-if="td.visibility">
            <span class="detail-label">能见度</span>
            <span class="detail-value">{{ td.visibility }}</span>
          </div>
          <div class="detail-item" v-if="td.pressure">
            <span class="detail-label">气压</span>
            <span class="detail-value">{{ td.pressure }}</span>
          </div>
        </div>

        <!-- 预报 -->
        <div v-if="forecastList.length" class="weather-forecast">
          <div class="forecast-title">天气预报</div>
          <div class="forecast-row">
            <div v-for="(day, i) in forecastList" :key="i" class="forecast-day">
              <div class="fc-day-name">{{ formatDay(day.day) }}</div>
              <div class="fc-condition">{{ forecastIcon(day.condition) }}</div>
              <div class="fc-temp">
                <span class="fc-high">{{ day.high }}</span>
                <span class="fc-low">{{ day.low }}</span>
              </div>
              <div class="fc-cond-text">{{ day.condition }}</div>
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
import BubbleChrome from './_shared/BubbleChrome.vue'

const props = defineProps<{ toolCall: ToolCall }>()
const emit = defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

const rawOutput = props.toolCall.output
if (rawOutput) {
  try {
    const parsed = JSON.parse(rawOutput)
    console.log('[WeatherBubble] raw output data keys:', Object.keys(parsed.data || {}), 'forecast:', JSON.stringify(parsed.data?.forecast?.slice(0, 2)))
  } catch {}
}

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

// ── 核心字段 ──
const cityName = computed(() => td.value.city || '未知城市')
const conditionText = computed(() => td.value.condition || '')
const windText = computed(() => td.value.wind || '')

// ── 温度解析 ──
const tempRaw = computed(() => String(td.value.temp || ''))
const tempValue = computed(() => {
  const m = tempRaw.value.match(/^(-?\d+\.?\d*)/)
  return m ? m[1] : tempRaw.value
})
const tempUnit = computed(() => {
  if (tempRaw.value.includes('°C') || tempRaw.value.includes('℃')) return '°C'
  if (tempRaw.value.includes('°F')) return '°F'
  return ''
})

// ── 天气背景色 ──
const bgGradient = computed(() => {
  const c = (conditionText.value || '').toLowerCase()
  if (c.includes('晴') && !c.includes('多云') && !c.includes('阴')) return 'linear-gradient(135deg, #2193b0, #6dd5ed)'
  if (c.includes('多云') || c.includes('阴')) return 'linear-gradient(135deg, #4b6cb7, #a8b8d8)'
  if (c.includes('雨') || c.includes('雷')) return 'linear-gradient(135deg, #2c3e50, #64748b)'
  if (c.includes('雪')) return 'linear-gradient(135deg, #a1c4fd, #c2e9fb)'
  if (c.includes('雾') || c.includes('霾')) return 'linear-gradient(135deg, #757f9a, #b8c6d6)'
  return 'linear-gradient(135deg, #2193b0, #6dd5ed)'
})

// ── 天气图标 ──
const conditionIcon = computed(() => {
  const c = (conditionText.value || '').toLowerCase()
  if (c.includes('雷')) return '⛈️'
  if (c.includes('雪')) return '❄️'
  if (c.includes('雨')) return '🌧️'
  if (c.includes('雾') || c.includes('霾')) return '🌫️'
  if (c.includes('晴') && !c.includes('多云')) return '☀️'
  if (c.includes('多云')) return '⛅'
  if (c.includes('阴')) return '☁️'
  if (c.includes('风')) return '💨'
  return '🌤️'
})

function forecastIcon(cond: string): string {
  const c = (cond || '').toLowerCase()
  if (c.includes('雷')) return '⛈️'
  if (c.includes('雪')) return '❄️'
  if (c.includes('雨')) return '🌧️'
  if (c.includes('晴') && !c.includes('多云')) return '☀️'
  if (c.includes('多云')) return '⛅'
  if (c.includes('阴') || c.includes('云')) return '☁️'
  return '🌤️'
}

// ── 详情 ──
const hasDetails = computed(() =>
  !!(td.value.humidity || td.value.temp_feel || td.value.visibility || td.value.pressure)
)

// ── 预报 ──
const forecastList = computed<Array<Record<string, any>>>(() => {
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

/* ── 主卡片 ── */
.weather-result {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 4px 0;
}

.weather-main {
  padding: 24px 20px;
  border-radius: 12px;
  color: #fff;
  text-align: center;
  box-shadow: 0 2px 12px rgba(0,0,0,0.1);
}

.weather-city {
  font-size: 16px;
  font-weight: 600;
  opacity: 0.95;
  margin-bottom: 4px;
}

.weather-temp {
  font-size: 56px;
  font-weight: 300;
  line-height: 1;
  margin: 8px 0;
}

.temp-unit {
  font-size: 24px;
  font-weight: 400;
  opacity: 0.8;
  vertical-align: super;
}

.weather-condition {
  font-size: 16px;
  opacity: 0.9;
  margin-bottom: 4px;
}

.weather-wind {
  font-size: 13px;
  opacity: 0.75;
}

/* ── 详情行 ── */
.weather-details {
  display: flex;
  gap: 1px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--border);
  background: var(--border);
}

.detail-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 10px 8px;
  background: var(--bg-primary);
}

.detail-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.detail-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

/* ── 预报 ── */
.weather-forecast {
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  background: var(--bg-primary);
}

.forecast-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  padding: 8px 12px 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.forecast-row {
  display: flex;
  padding: 4px 12px 12px;
  gap: 4px;
  overflow-x: auto;
}

.forecast-day {
  flex: 1;
  min-width: 60px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 6px 4px;
  border-radius: 6px;
  background: var(--bg-secondary);
}

.fc-day-name {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-primary);
}

.fc-condition {
  font-size: 18px;
  line-height: 1;
}

.fc-temp {
  display: flex;
  gap: 4px;
  font-size: 12px;
}

.fc-high {
  font-weight: 600;
  color: #e06050;
}

.fc-low {
  color: var(--text-secondary);
}

.fc-cond-text {
  font-size: 10px;
  color: var(--text-secondary);
  text-align: center;
  line-height: 1.2;
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
