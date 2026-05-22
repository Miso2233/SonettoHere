<template>
  <BubbleChrome :tool-call="toolCall">
    <!-- 运行中 -->
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>{{ runningLabel }}</span>
    </div>

    <!-- 错误 -->
    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '查询失败' }}
    </div>

    <!-- 完成 -->
    <template v-else-if="toolCall.status === 'done'">
      <div v-if="hasData" class="map-result">

        <!-- ===== nearby_search / fuzzy_address_search  POI 列表 ===== -->
        <template v-if="isPoiTool">
          <div class="map-header">
            <span class="map-icon">📍</span>
            <div class="map-header-text">
              <div class="map-title">{{ headerTitle }}</div>
              <div class="map-subtitle">{{ poiSubtitle }}</div>
            </div>
          </div>
          <div class="map-stats">
            <span class="stat-tag">共 {{ poiCount }} 个结果</span>
            <span v-if="td.radius" class="stat-tag">半径 {{ td.radius }}m</span>
            <span v-if="td.city" class="stat-tag">{{ td.city }}</span>
          </div>
          <div class="poi-list">
            <div v-for="(poi, i) in poiList" :key="i" class="poi-item">
              <span class="poi-idx">{{ i + 1 }}</span>
              <div class="poi-body">
                <div class="poi-name">{{ poi.name }}</div>
                <div class="poi-addr">{{ poi.address || '暂无地址' }}</div>
                <div class="poi-meta">
                  <span v-if="poi.type" class="poi-type">{{ shortType(poi.type) }}</span>
                  <span v-if="poi.cityname" class="poi-city">{{ poi.cityname }}</span>
                  <span v-if="poi.distance" class="poi-dist">{{ poi.distance }}</span>
                </div>
              </div>
            </div>
          </div>
          <div class="map-actions">
            <button
              v-if="td.location"
              class="action-btn"
              @click="copyCoord"
            >
              复制中心坐标
            </button>
          </div>
        </template>

        <!-- ===== geocode_address 坐标结果 ===== -->
        <template v-else-if="isGeocode">
          <div class="map-header">
            <span class="map-icon">📍</span>
            <div class="map-header-text">
              <div class="map-title">地理编码</div>
              <div class="map-subtitle">地址 → 坐标</div>
            </div>
          </div>
          <div class="geocode-result">
            <div class="gc-row">
              <span class="gc-label">地址</span>
              <span class="gc-value">{{ td.address }}</span>
            </div>
            <div class="gc-row">
              <span class="gc-label">坐标</span>
              <span class="gc-value coord">{{ td.location }}</span>
            </div>
          </div>
          <div class="map-actions">
            <button
              v-if="td.location"
              class="action-btn"
              @click="copyCoord"
            >
              复制坐标
            </button>
          </div>
        </template>

        <!-- ===== get_transit_route 公交换乘 ===== -->
        <template v-else-if="isTransit">
          <div class="map-header">
            <span class="map-icon">🚌</span>
            <div class="map-header-text">
              <div class="map-title">公交换乘</div>
              <div class="map-subtitle">{{ transitRoute }}</div>
            </div>
          </div>
          <div class="map-stats" v-if="routeCount">
            <span class="stat-tag">共 {{ routeCount }} 个方案</span>
          </div>
          <div class="route-list">
            <div v-for="(route, ri) in transitRoutes" :key="ri" class="route-card">
              <div class="route-card-header">
                <span class="route-label">方案 {{ ri + 1 }}</span>
                <span class="route-cost">💰 {{ route.cost }}元</span>
                <span class="route-duration">⏱ {{ formatDuration(route.duration) }}</span>
                <span v-if="route.walking_distance" class="route-walk">🚶 {{ route.walking_distance }}m</span>
              </div>
              <div class="route-segments">
                <div v-for="(seg, si) in route.segments" :key="si" class="segment">
                  <template v-if="seg.walking">
                    <div class="seg-walk">
                      <span class="seg-icon">🚶</span>
                      <span>步行 {{ seg.walking.distance }}m</span>
                    </div>
                  </template>
                  <template v-if="seg.bus">
                    <div v-for="(line, li) in seg.bus.lines" :key="li" class="seg-bus">
                      <span class="seg-icon">🚌</span>
                      <span class="seg-line">{{ line.name }}</span>
                      <span class="seg-stops">{{ line.departure_stop }} → {{ line.arrival_stop }}</span>
                      <span class="seg-meta">{{ line.via_num }} 站 · {{ formatDuration(line.duration) }}</span>
                    </div>
                  </template>
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- ===== get_cycling_route 骑行路线 ===== -->
        <template v-else-if="isCycling">
          <div class="map-header">
            <span class="map-icon">🚴</span>
            <div class="map-header-text">
              <div class="map-title">骑行路线</div>
              <div class="map-subtitle">{{ cyclingRoute }}</div>
            </div>
          </div>
          <div class="map-stats" v-if="pathCount">
            <span class="stat-tag">共 {{ pathCount }} 条路线</span>
          </div>
          <div class="route-list">
            <div v-for="(path, pi) in cyclingPaths" :key="pi" class="route-card">
              <div class="route-card-header">
                <span class="route-label">路线 {{ pi + 1 }}</span>
                <span class="route-duration">⏱ {{ formatDuration(path.duration) }}</span>
                <span class="route-dist">📏 {{ formatDistance(path.distance) }}</span>
              </div>
              <div class="cycling-steps" v-if="path.steps && path.steps.length">
                <div v-for="(step, si) in path.steps.slice(0, 8)" :key="si" class="cycling-step">
                  <span class="step-idx">{{ si + 1 }}</span>
                  <div class="step-body">
                    <span class="step-instr">{{ step.instruction }}</span>
                    <span class="step-meta">
                      {{ step.road }} · {{ formatDistance(step.distance) }}
                    </span>
                  </div>
                </div>
                <div v-if="path.steps.length > 8" class="steps-more">
                  ... 共 {{ path.steps.length }} 个转向指令
                </div>
              </div>
            </div>
          </div>
        </template>

      </div>

      <!-- 降级：toolData 缺失 -->
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

// ── 数据源：优先 toolData，降级到 parse output ──
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

const toolName = computed(() => props.toolCall.name)

const isPoiTool = computed(() =>
  toolName.value === 'nearby_search' || toolName.value === 'fuzzy_address_search'
)

const isGeocode = computed(() => toolName.value === 'geocode_address')

const isTransit = computed(() => toolName.value === 'get_transit_route')

const isCycling = computed(() => toolName.value === 'get_cycling_route')

// ── 运行中提示 ──
const runningLabel = computed(() => {
  switch (toolName.value) {
    case 'nearby_search': return '正在搜索周边...'
    case 'fuzzy_address_search': return '正在搜索地点...'
    case 'geocode_address': return '正在解析地址...'
    case 'get_transit_route': return '正在规划公交路线...'
    case 'get_cycling_route': return '正在规划骑行路线...'
    default: return '查询中...'
  }
})

// ── POI 工具 ──
const headerTitle = computed(() => {
  if (isPoiTool.value) {
    if (toolName.value === 'nearby_search') return '周边搜索'
    return '地点搜索'
  }
  return ''
})

const poiSubtitle = computed(() => {
  if (toolName.value === 'nearby_search') {
    const kw = td.value.keywords || ''
    const loc = td.value.location || ''
    return kw ? `"${kw}" · ${loc}` : loc
  }
  if (toolName.value === 'fuzzy_address_search') {
    const kw = td.value.keywords || ''
    const city = td.value.city || ''
    return city ? `"${kw}" · ${city}` : `"${kw}"`
  }
  return ''
})

const poiCount = computed(() => {
  const count = td.value.count
  return count ?? td.value.pois?.length ?? 0
})

const poiList = computed<Array<Record<string, any>>>(() => {
  const pois = td.value.pois
  return Array.isArray(pois) ? pois : []
})

function shortType(type: string): string {
  if (!type) return ''
  const parts = type.split(';')
  return parts[parts.length - 1]?.trim() || type
}

// ── 地理编码 ──

// ── 公交换乘 ──
const transitRoute = computed(() => {
  const o = td.value.origin || ''
  const d = td.value.destination || ''
  return o && d ? `${o} → ${d}` : ''
})

const routeCount = computed(() => td.value.route_count ?? 0)

const transitRoutes = computed<Array<Record<string, any>>>(() => {
  const routes = td.value.routes
  return Array.isArray(routes) ? routes : []
})

// ── 骑行路线 ──
const cyclingRoute = computed(() => {
  const o = td.value.origin || ''
  const d = td.value.destination || ''
  return o && d ? `${o} → ${d}` : ''
})

const pathCount = computed(() => td.value.path_count ?? 0)

const cyclingPaths = computed<Array<Record<string, any>>>(() => {
  const paths = td.value.paths
  return Array.isArray(paths) ? paths : []
})

// ── 格式化 ──
function formatDuration(seconds: number): string {
  if (!seconds && seconds !== 0) return ''
  const mins = Math.round(seconds / 60)
  if (mins < 60) return `${mins} 分钟`
  const h = Math.floor(mins / 60)
  const m = mins % 60
  return m > 0 ? `${h} 小时 ${m} 分钟` : `${h} 小时`
}

function formatDistance(meters: number): string {
  if (!meters && meters !== 0) return ''
  if (meters < 1000) return `${meters} m`
  return `${(meters / 1000).toFixed(1)} km`
}

// ── 交互 ──
function copyCoord() {
  const loc = td.value.location
  if (!loc) return
  navigator.clipboard.writeText(String(loc))
  emit('action', { action: 'copy', data: { text: loc } })
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

/* ── 地图公共 ── */
.map-result {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 4px 0;
}

.map-header {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.map-icon {
  font-size: 22px;
  line-height: 1.3;
  flex-shrink: 0;
}

.map-header-text {
  flex: 1;
  min-width: 0;
}

.map-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.map-subtitle {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.map-stats {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.stat-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  font-weight: 500;
}

/* ── POI 列表 ── */
.poi-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.poi-item {
  display: flex;
  gap: 10px;
  padding: 10px 12px;
  background: var(--bg-primary);
  border-radius: 8px;
  border: 1px solid var(--border);
}

.poi-idx {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  font-size: 11px;
  font-weight: 600;
  color: #fff;
  background: #4a90d9;
  border-radius: 4px;
  flex-shrink: 0;
  line-height: 20px;
}

.poi-body {
  flex: 1;
  min-width: 0;
}

.poi-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.4;
}

.poi-addr {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.poi-meta {
  display: flex;
  gap: 6px;
  margin-top: 4px;
  flex-wrap: wrap;
}

.poi-type {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  background: #e8f0fe;
  color: #1a73e8;
}

.poi-city {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
}

.poi-dist {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  background: #e8f5e8;
  color: #2d6a2d;
}

/* ── 地理编码 ── */
.geocode-result {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  background: var(--bg-primary);
  border-radius: 8px;
  border: 1px solid var(--border);
}

.gc-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.gc-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  min-width: 40px;
}

.gc-value {
  font-size: 14px;
  color: var(--text-primary);
  word-break: break-all;
}

.gc-value.coord {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 13px;
  color: #4a90d9;
  font-weight: 500;
  background: var(--bg-secondary);
  padding: 3px 8px;
  border-radius: 4px;
}

/* ── 路线 ── */
.route-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.route-card {
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-primary);
  overflow: hidden;
}

.route-card-header {
  display: flex;
  gap: 10px;
  padding: 8px 12px;
  background: var(--bg-secondary);
  flex-wrap: wrap;
  align-items: center;
}

.route-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent);
}

.route-cost,
.route-duration,
.route-walk,
.route-dist {
  font-size: 11px;
  color: var(--text-secondary);
}

.route-segments {
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.segment {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.seg-walk,
.seg-bus {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-primary);
  padding: 2px 0;
}

.seg-icon {
  flex-shrink: 0;
  font-size: 13px;
}

.seg-line {
  font-weight: 600;
  color: #1a73e8;
}

.seg-stops {
  color: var(--text-secondary);
  font-size: 11px;
}

.seg-meta {
  color: var(--text-secondary);
  font-size: 11px;
  margin-left: auto;
}

/* ── 骑行指令 ── */
.cycling-steps {
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cycling-step {
  display: flex;
  gap: 8px;
  padding: 4px 0;
  border-bottom: 1px solid var(--border);
}

.cycling-step:last-child {
  border-bottom: none;
}

.step-idx {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-secondary);
  min-width: 16px;
  line-height: 1.6;
}

.step-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.step-instr {
  font-size: 12px;
  color: var(--text-primary);
  line-height: 1.4;
}

.step-meta {
  font-size: 11px;
  color: var(--text-secondary);
}

.steps-more {
  font-size: 11px;
  color: var(--text-secondary);
  text-align: center;
  padding: 4px 0;
  opacity: 0.7;
}

/* ── 操作按钮 ── */
.map-actions {
  display: flex;
  gap: 6px;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}

.action-btn:hover {
  background: var(--bg-secondary);
  border-color: var(--accent-light);
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
