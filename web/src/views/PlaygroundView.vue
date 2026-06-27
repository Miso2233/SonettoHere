<template>
  <div class="playground">
    <header class="pg-header">
      <div class="pg-header-left">
        <h1 class="pg-title">Kaleidoscope Playground</h1>
        <span class="pg-badge">开发专用</span>
      </div>
      <div class="pg-header-right">
        <span class="pg-stats">
          已注册 <strong>{{ registeredCount }}</strong> / <strong>{{ toolNames.length }}</strong> 个工具
        </span>
      </div>
    </header>

    <div class="pg-body">
      <!-- 左侧：工具列表 -->
      <aside class="pg-sidebar">
        <div class="pg-section-title">工具列表</div>
        <div class="tool-list">
          <div
            v-for="toolName in toolNames"
            :key="toolName"
            class="tool-item"
            :class="{ active: selectedTool === toolName }"
            @click="selectTool(toolName)"
          >
            <span class="tool-dot" :class="{ registered: isRegistered(toolName) }"></span>
            <span class="tool-item-name">{{ toolDisplayName(toolName) }}</span>
            <span class="tool-item-id">{{ toolName }}</span>
            <span v-if="isRegistered(toolName)" class="chip registered">专属</span>
            <span v-else class="chip fallback">兜底</span>
          </div>
        </div>
      </aside>

      <!-- 右侧：预览区 -->
      <div class="pg-main">
        <!-- 状态切换 -->
        <div class="state-bar">
          <span class="state-bar-label">状态切换：</span>
          <button
            v-for="s in states"
            :key="s"
            class="state-btn"
            :class="s"
            @click="currentState = s"
          >
            <span class="state-dot" :class="s"></span>
            {{ stateLabel(s) }}
          </button>
        </div>

        <!-- 气泡预览 -->
        <div class="preview-area">
          <div class="preview-header">
            <span class="preview-label">
              {{ toolDisplayName(selectedTool) }}
              <code class="preview-tool-id">{{ selectedTool }}</code>
            </span>
            <span v-if="isRegistered(selectedTool)" class="preview-using">
              使用 {{ getBubbleComponentName(selectedTool) }}
            </span>
            <span v-else class="preview-using fallback-text">
              使用 ToolCallCard（兜底）
            </span>
          </div>
          <div class="preview-body">
            <ToolBubbleRouter
              :key="selectedTool + ':' + currentState"
              :tool-call="currentMock"
              @action="logAction"
            />
          </div>
        </div>

        <!-- 交互日志 -->
        <div class="action-log">
          <div class="action-log-header">
            <span class="pg-section-title">交互日志</span>
            <button
              v-if="actionLog.length > 0"
              class="clear-btn"
              @click="actionLog = []"
            >
              清空
            </button>
          </div>
          <div class="log-entries">
            <div
              v-for="(entry, i) in actionLog"
              :key="i"
              class="log-entry"
            >
              <span class="log-idx">#{{ actionLog.length - i }}</span>
              <span class="log-time">{{ entry.time }}</span>
              <span class="log-action">{{ entry.action }}</span>
              <code v-if="entry.data" class="log-data">{{ entry.data }}</code>
            </div>
            <div v-if="actionLog.length === 0" class="log-empty">
              点击气泡中的交互组件以记录事件
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ToolCall } from '@/types'
import ToolBubbleRouter from '@/components/ToolBubbleRouter.vue'
import { getRegisteredTools } from '@/components/tools/registry'
import { toolDisplayName, ALL_TOOL_NAMES } from '@/components/tools/_shared/displayNames'

// ── 状态定义 ──
type ToolStatus = 'running' | 'done' | 'error'
const states: ToolStatus[] = ['running', 'done', 'error']
const stateLabels: Record<ToolStatus, string> = {
  running: '运行中',
  done: '已完成',
  error: '出错',
}

const toolNames = ALL_TOOL_NAMES
const registeredTools = getRegisteredTools()

function isRegistered(name: string): boolean {
  return registeredTools.includes(name)
}

const registeredCount = computed(() => registeredTools.length)

function stateLabel(s: ToolStatus): string {
  return stateLabels[s]
}

function getBubbleComponentName(name: string): string {
  const map: Record<string, string> = {
    'todo_add': 'TodoBubble.vue',
    'todo_list': 'TodoBubble.vue',
    'todo_complete': 'TodoBubble.vue',
    'todo_uncomplete': 'TodoBubble.vue',
    'todo_delete': 'TodoBubble.vue',
    'todo_update': 'TodoBubble.vue',
    'todo_query': 'TodoBubble.vue',
    'todo_list_projects': 'TodoBubble.vue → ProjectTreeBubble',
    'todo_add_quick': 'TodoBubble.vue → ActionResultBubble',
    'todo_list_sections': 'TodoBubble.vue → SectionListBubble',
    'todo_list_labels': 'TodoBubble.vue → LabelListBubble',
    'task_tracker': 'TaskTrackerBubble.vue',
    'run_python': 'PythonBubble.vue',
    'file_read': 'FilesBubble.vue',
    'file_write': 'FilesBubble.vue',
    'file_list': 'FilesBubble.vue',
    'file_operations': 'FilesBubble.vue',
    'tarot': 'TarotBubble.vue',
    'nearby_search': 'MapBubble.vue',
    'fuzzy_address_search': 'MapBubble.vue',
    'geocode_address': 'MapBubble.vue',
    'get_transit_route': 'MapBubble.vue',
    'get_cycling_route': 'MapBubble.vue',
    'get_current_weather': 'WeatherBubble.vue',
    'holiday_calendar': 'HolidayBubble.vue',
    'analyze_image': 'ImageBubble.vue',
    'tavily_search': 'TavilySearchBubble.vue',
    'tavily_extract': 'TavilyExtractBubble.vue',
  }
  return map[name] ?? name
}

// ── 选中工具与状态 ──
const selectedTool = ref(toolNames[0])
const currentState = ref<ToolStatus>('done')

function selectTool(name: string) {
  selectedTool.value = name
  currentState.value = 'done'
}

// ── Mock 数据生成 ──
const currentMock = computed<ToolCall>(() => {
  return buildMock(selectedTool.value, currentState.value)
})

interface MockTemplate {
  input: Record<string, unknown>
  doneOutput: string
  toolData?: Record<string, unknown>
}

const mockTemplates: Record<string, MockTemplate> = {
  weather: {
    input: { city: '京都', date: '2026-05-16' },
    doneOutput: JSON.stringify({
      success: true,
      data: {
        city: '京都',
        temp: '22°C',
        humidity: '65%',
        condition: '晴转多云',
        wind: '东北风 3级',
        report_time: '2026-05-16 12:00',
        forecast: [
          { day: '今天', high: '25°C', low: '18°C', condition: '晴转多云', sunrise: '04:52', sunset: '18:45', pop: '10%', humidity: '60%' },
          { day: '明天', high: '27°C', low: '19°C', condition: '晴', sunrise: '04:53', sunset: '18:46', pop: '0%', humidity: '55%' },
          { day: '后天', high: '23°C', low: '17°C', condition: '小雨', sunrise: '04:54', sunset: '18:47', pop: '70%', humidity: '85%' },
        ],
      },
    }),
  },
  get_current_weather: {
    input: { city: '北京', forecast: true, extended: true },
    doneOutput: JSON.stringify({
      success: true,
      data: {
        city: '北京',
        temp: '26°C',
        humidity: '45%',
        condition: '晴',
        wind: '南风 2级',
        report_time: '2026-06-27 14:00',
        temp_feel: '27°C',
        visibility: '10km',
        pressure: '1013hPa',
        aqi: 72,
        aqi_level: '2',
        aqi_category: '良',
        aqi_primary: 'PM2.5',
        uv: 6,
        alerts: [
          { title: '大风蓝色预警', type: '大风', level: 'blue', text: '预计未来24小时本市有4-5级偏北风，阵风7级左右，请注意防范。', publish_time: '2026-06-27 10:00', publisher: '北京市气象台', guidance: ['外出注意防风', '远离广告牌' ] },
        ],
        forecast: [
          { day: '今天', high: '28°C', low: '18°C', condition: '晴', sunrise: '04:48', sunset: '19:42', pop: '5%', humidity: '40%' },
          { day: '明天', high: '30°C', low: '20°C', condition: '晴转多云', sunrise: '04:49', sunset: '19:42', pop: '15%', humidity: '45%' },
          { day: '后天', high: '27°C', low: '19°C', condition: '多云', sunrise: '04:50', sunset: '19:43', pop: '0%', humidity: '55%' },
          { day: '周四', high: '25°C', low: '17°C', condition: '小雨', sunrise: '04:51', sunset: '19:44', pop: '60%', humidity: '80%' },
          { day: '周五', high: '24°C', low: '16°C', condition: '阴', sunrise: '04:52', sunset: '19:45', pop: '20%', humidity: '70%' },
        ],
      },
    }),
    toolData: {
      city: '北京',
      temp: '26°C',
      humidity: '45%',
      condition: '晴',
      wind: '南风 2级',
      update_time: '2026-06-27 14:00',
      temp_feel: '27°C',
      visibility: '10km',
      pressure: '1013hPa',
      aqi: 72,
      aqi_category: '良',
      uv: 6,
      alerts: [
        { title: '大风蓝色预警', type: '大风', level: 'blue', text: '预计未来24小时本市有4-5级偏北风，阵风7级左右，请注意防范。', publish_time: '2026-06-27 10:00', publisher: '北京市气象台', guidance: ['外出注意防风', '远离广告牌'] },
      ],
      forecast: [
        { day: '今天', high: '28°C', low: '18°C', condition: '晴', sunrise: '04:48', sunset: '19:42', pop: '5%', humidity: '40%' },
        { day: '明天', high: '30°C', low: '20°C', condition: '晴转多云', sunrise: '04:49', sunset: '19:42', pop: '15%', humidity: '45%' },
        { day: '后天', high: '27°C', low: '19°C', condition: '多云', sunrise: '04:50', sunset: '19:43', pop: '0%', humidity: '55%' },
        { day: '周四', high: '25°C', low: '17°C', condition: '小雨', sunrise: '04:51', sunset: '19:44', pop: '60%', humidity: '80%' },
        { day: '周五', high: '24°C', low: '16°C', condition: '阴', sunrise: '04:52', sunset: '19:45', pop: '20%', humidity: '70%' },
      ],
    },
  },
  holiday_calendar: {
    input: { date: '2026-10-01', include_nearby: true, nearby_limit: 5 },
    doneOutput: JSON.stringify({
      success: true,
      data: {
        mode: 'day',
        query: { date: '2026-10-01', holiday_type: 'all', include_nearby: true, exclude_past: true, month: '', nearby_limit: 5, timezone: 'Asia/Shanghai', year: '' },
        summary: { total_days: 1, weekend_days: 0, workdays: 0, rest_days: 1, holiday_events: 2, legal_rest_days: 1, legal_workdays: 0 },
        days: [
          { date: '2026-10-01', year: 2026, month: 10, day: 1, weekday_cn: '星期四', is_weekend: false, is_workday: false, is_rest_day: true, is_holiday: true, legal_holiday_name: '国庆节', legal_holiday_type: 'rest', solar_festival: '国庆节', lunar_festival: '', solar_term: '', lunar_year: 2026, lunar_month: 8, lunar_day: 21, lunar_month_name: '八月', lunar_day_name: '廿一', ganzhi_year: '乙巳', ganzhi_month: '乙酉', ganzhi_day: '癸卯' },
        ],
        holidays: [
          { date: '2026-10-01', name: '国庆节', type: 'legal_rest' },
          { date: '2026-10-01', name: '国际音乐节', type: 'solar' },
        ],
        nearby: {
          previous: [{ date: '2026-09-28', events: [{ date: '2026-09-28', name: '国庆调休', type: 'legal_workday_adjust', is_workday: true }] }],
          next: [
            { date: '2026-10-02', events: [{ date: '2026-10-02', name: '国庆节', type: 'legal_rest', is_workday: false }] },
            { date: '2026-10-29', events: [{ date: '2026-10-29', name: '重阳节', type: 'lunar', is_workday: false }] },
          ],
        },
      },
    }),
    toolData: {
      mode: 'day',
      date: '2026-10-01',
      weekday: '星期四',
      lunar_date: '八月廿一',
      days: [
        { date: '2026-10-01', weekday: '星期四', lunar_date: '八月廿一', lunar_month: '八月', lunar_day: '廿一', legal_holiday_name: '国庆节', solar_festival: '国庆节', lunar_festival: '', solar_term: '', is_rest_day: true, is_holiday: true, ganzhi_year: '乙巳', ganzhi_month: '乙酉', ganzhi_day: '癸卯' },
      ],
      holidays: [
        { name: '国庆节', type: 'legal_rest', date: '2026-10-01' },
        { name: '国际音乐节', type: 'solar', date: '2026-10-01' },
      ],
      nearby: {
        previous: [{ date: '2026-09-28', events: [{ name: '国庆调休', type: 'legal_workday_adjust', date: '2026-09-28' }] }],
        next: [
          { date: '2026-10-02', events: [{ name: '国庆节', type: 'legal_rest', date: '2026-10-02' }] },
          { date: '2026-10-29', events: [{ name: '重阳节', type: 'lunar', date: '2026-10-29' }] },
        ],
      },
    },
  },
  map_nearby: {
    input: { location: '岚山', radius: 2000, keywords: '咖啡' },
    doneOutput: JSON.stringify({
      success: true,
      data: {
        pois: [
          { name: 'Arabica 京都岚山', address: '京都府京都市右京区嵯峨天龙寺芒ノ马场町3-47', distance: '120m', rating: '4.6' },
          { name: 'Bread & Espresso &', address: '京都府京都市右京区嵯峨天龙寺造路町18-4', distance: '350m', rating: '4.3' },
          { name: '咖啡馆 嵯峨野', address: '京都府京都市右京区嵯峨天竜寺瀬戸川町6-1', distance: '580m', rating: '4.1' },
        ],
      },
    }),
  },
  nearby_search: {
    input: { location: '116.481028,39.989643', radius: 2000, keywords: '咖啡' },
    doneOutput: JSON.stringify({
      success: true,
      data: {
        location: '116.481028,39.989643',
        keywords: '咖啡',
        radius: 2000,
        count: 3,
        pois: [
          { id: 'POI001', name: '星巴克（望京SOHO店）', location: '116.480,39.990', address: '北京市朝阳区望京SOHO T1一层', cityname: '北京市', adname: '朝阳区', type: '餐饮服务;咖啡厅' },
          { id: 'POI002', name: '瑞幸咖啡（融科店）', location: '116.483,39.987', address: '北京市海淀区科学院南路2号', cityname: '北京市', adname: '海淀区', type: '餐饮服务;咖啡厅' },
          { id: 'POI003', name: 'Costa Coffee（中关村店）', location: '116.485,39.985', address: '北京市海淀区中关村大街15号', cityname: '北京市', adname: '海淀区', type: '餐饮服务;咖啡厅' },
        ],
      },
    }),
    toolData: {
      location: '116.481028,39.989643',
      keywords: '咖啡',
      radius: 2000,
      count: 3,
      pois: [
        { name: '星巴克（望京SOHO店）', address: '北京市朝阳区望京SOHO T1一层', location: '116.480,39.990', cityname: '北京市', adname: '朝阳区', type: '餐饮服务;咖啡厅' },
        { name: '瑞幸咖啡（融科店）', address: '北京市海淀区科学院南路2号', location: '116.483,39.987', cityname: '北京市', adname: '海淀区', type: '餐饮服务;咖啡厅' },
        { name: 'Costa Coffee（中关村店）', address: '北京市海淀区中关村大街15号', location: '116.485,39.985', cityname: '北京市', adname: '海淀区', type: '餐饮服务;咖啡厅' },
      ],
    },
  },
  fuzzy_address_search: {
    input: { keywords: '北京大学', city: '北京' },
    doneOutput: JSON.stringify({
      success: true,
      data: {
        keywords: '北京大学',
        city: '北京',
        count: 2,
        pois: [
          { id: 'POI010', name: '北京大学', location: '116.310,39.992', address: '北京市海淀区颐和园路5号', cityname: '北京市', adname: '海淀区', type: '科教文化服务;高等院校' },
          { id: 'POI011', name: '北京大学医学部', location: '116.353,39.977', address: '北京市海淀区学院路38号', cityname: '北京市', adname: '海淀区', type: '科教文化服务;高等院校' },
        ],
      },
    }),
    toolData: {
      keywords: '北京大学',
      city: '北京',
      count: 2,
      pois: [
        { name: '北京大学', location: '116.310,39.992', address: '北京市海淀区颐和园路5号', cityname: '北京市', adname: '海淀区', type: '科教文化服务;高等院校' },
        { name: '北京大学医学部', location: '116.353,39.977', address: '北京市海淀区学院路38号', cityname: '北京市', adname: '海淀区', type: '科教文化服务;高等院校' },
      ],
    },
  },
  geocode_address: {
    input: { address: '北京市海淀区中关村大街' },
    doneOutput: JSON.stringify({
      success: true,
      data: { address: '北京市海淀区中关村大街', location: '116.324,39.951' },
    }),
    toolData: {
      address: '北京市海淀区中关村大街',
      location: '116.324,39.951',
    },
  },
  get_transit_route: {
    input: { origin_longitude: '116.4', origin_latitude: '39.9', destination_longitude: '116.27', destination_latitude: '39.99', origin_city: '北京', destination_city: '北京' },
    doneOutput: JSON.stringify({
      success: true,
      data: {
        origin: '116.4,39.9',
        destination: '116.27,39.99',
        origin_city: '北京',
        destination_city: '北京',
        route_count: 2,
        routes: [
          { cost: 5, duration: 1860, walking_distance: 320, segments: [{ walking: { distance: 320, steps: [] }, bus: { lines: [{ type: '地铁', name: '地铁1号线', departure_stop: '王府井', arrival_stop: '天安门东', via_num: 1, distance: 1200, duration: 180 }] } }, { bus: { lines: [{ type: '公交', name: '332路', departure_stop: '天安门东', arrival_stop: '颐和园', via_num: 14, distance: 12000, duration: 2400 }] } }] },
          { cost: 4, duration: 2400, walking_distance: 150, segments: [{ walking: { distance: 150, steps: [] }, bus: { lines: [{ type: '地铁', name: '地铁4号线', departure_stop: '西单', arrival_stop: '北宫门', via_num: 10, distance: 15000, duration: 1800 }] } }, { walking: { distance: 800, steps: [] } }] },
        ],
      },
    }),
    toolData: {
      origin: '116.4,39.9',
      destination: '116.27,39.99',
      origin_city: '北京',
      destination_city: '北京',
      route_count: 2,
      routes: [
        { cost: 5, duration: 1860, walking_distance: 320, segments: [{ walking: { distance: 320, steps: [] }, bus: { lines: [{ type: '地铁', name: '地铁1号线', departure_stop: '王府井', arrival_stop: '天安门东', via_num: 1, distance: 1200, duration: 180 }] } }, { bus: { lines: [{ type: '公交', name: '332路', departure_stop: '天安门东', arrival_stop: '颐和园', via_num: 14, distance: 12000, duration: 2400 }] } }] },
        { cost: 4, duration: 2400, walking_distance: 150, segments: [{ walking: { distance: 150, steps: [] }, bus: { lines: [{ type: '地铁', name: '地铁4号线', departure_stop: '西单', arrival_stop: '北宫门', via_num: 10, distance: 15000, duration: 1800 }] } }, { walking: { distance: 800, steps: [] } }] },
      ],
    },
  },
  get_cycling_route: {
    input: { origin_longitude: '116.4', origin_latitude: '39.9', destination_longitude: '116.27', destination_latitude: '39.99' },
    doneOutput: JSON.stringify({
      success: true,
      data: {
        origin: '116.4,39.9',
        destination: '116.27,39.99',
        path_count: 1,
        paths: [
          { distance: 8500, duration: 2700, steps: [
            { instruction: '沿王府井大街向北骑行', orientation: '北', road: '王府井大街', distance: 1200, duration: 300, action: '直行', assistant_action: '' },
            { instruction: '左转进入长安街', orientation: '西', road: '长安街', distance: 2500, duration: 600, action: '左转', assistant_action: '' },
            { instruction: '沿长安街向西骑行', orientation: '西', road: '长安街', distance: 3000, duration: 720, action: '直行', assistant_action: '' },
            { instruction: '右转进入颐和园路', orientation: '北', road: '颐和园路', distance: 1800, duration: 480, action: '右转', assistant_action: '' },
            { instruction: '到达目的地颐和园东门', orientation: '', road: '', distance: 0, duration: 0, action: '到达', assistant_action: '' },
          ]},
        ],
      },
    }),
    toolData: {
      origin: '116.4,39.9',
      destination: '116.27,39.99',
      path_count: 1,
      paths: [
        { distance: 8500, duration: 2700, steps: [
          { instruction: '沿王府井大街向北骑行', orientation: '北', road: '王府井大街', distance: 1200, duration: 300, action: '直行', assistant_action: '' },
          { instruction: '左转进入长安街', orientation: '西', road: '长安街', distance: 2500, duration: 600, action: '左转', assistant_action: '' },
          { instruction: '沿长安街向西骑行', orientation: '西', road: '长安街', distance: 3000, duration: 720, action: '直行', assistant_action: '' },
          { instruction: '右转进入颐和园路', orientation: '北', road: '颐和园路', distance: 1800, duration: 480, action: '右转', assistant_action: '' },
          { instruction: '到达目的地颐和园东门', orientation: '', road: '', distance: 0, duration: 0, action: '到达', assistant_action: '' },
        ]},
      ],
    },
  },
  search: {
    input: { query: '京都红叶最佳观赏时间' },
    doneOutput: '京都红叶最佳观赏期为**11月中旬至12月上旬**。\n\n推荐地点：\n- 岚山（竹林+红叶）\n- 永观堂（夜枫名所）\n- 东福寺（通天桥）\n- 清水寺（夜间特别参拜）',
  },
  tavily_search: {
    input: { query: '2026 AI Agent 框架对比' },
    doneOutput: JSON.stringify({
      success: true,
      data: {
        query: 'Go最新的版本是多少',
        total_results: 15,
        results: [
          { title: 'Go 1.26 正式发布', url: 'https://go.dev/blog/go1.26', snippet: '2026年2月10日，Go 团队正式发布了 Go 1.26 版本，包含泛型性能改进和新的迭代器支持。', domain: 'go.dev', source: 'uapi-searchv1', position: 1, score: 0.93, publish_time: '2026-02-10T00:00:00Z' },
          { title: 'Go 1.25 新特性一览', url: 'https://go.dev/blog/go1.25', snippet: 'Go 1.25 引入了增强的错误处理机制和改进的交叉编译支持。', domain: 'go.dev', source: 'uapi-searchv1', position: 2, score: 0.88, publish_time: '2025-08-15T00:00:00Z' },
          { title: 'Go 语言入门教程', url: 'https://example.com/go-tutorial', snippet: '本文从零开始介绍 Go 语言的基础语法、并发编程和标准库使用。', domain: 'example.com', source: 'uapi-searchv1', position: 3, score: 0.75, publish_time: '2025-06-20T00:00:00Z' },
          { title: 'Go 泛型实战：重构遗留代码', url: 'https://example.com/go-generics', snippet: '通过实际案例学习如何利用 Go 泛型重构现有代码，提高代码复用性和类型安全性。', domain: 'example.com', source: 'uapi-searchv1', position: 4, score: 0.71, publish_time: '' },
          { title: '高效 Go 编程：性能优化指南', url: 'https://github.com/go-perf-guide', snippet: '一份全面的 Go 性能优化清单，涵盖内存管理、并发调度和编译器优化技巧。', domain: 'github.com', source: 'uapi-searchv1', position: 5, score: 0.65, publish_time: '2025-12-01T00:00:00Z' },
        ],
        sources: [
          { name: 'uapi-searchv1', status: 'success', result_count: 15, elapsed_ms: 3675, first_result_host: 'go.dev' },
        ],
        process_time_ms: 3675,
        metadata: {
          request_params: { query: 'Go最新的版本是多少', limit: 10, page: 1, timeout_ms: 60000, sort: 'relevance' },
          dedupe_removed: 0,
          rerank_applied: true,
          content_fetched: 0,
        },
      },
    }),
    toolData: {
      query: 'Go最新的版本是多少',
      total_results: 15,
      results: [
        { title: 'Go 1.26 正式发布', url: 'https://go.dev/blog/go1.26', snippet: '2026年2月10日，Go 团队正式发布了 Go 1.26 版本，包含泛型性能改进和新的迭代器支持。', domain: 'go.dev', source: 'uapi-searchv1', position: 1, score: 0.93, publish_time: '2026-02-10T00:00:00Z' },
        { title: 'Go 1.25 新特性一览', url: 'https://go.dev/blog/go1.25', snippet: 'Go 1.25 引入了增强的错误处理机制和改进的交叉编译支持。', domain: 'go.dev', source: 'uapi-searchv1', position: 2, score: 0.88, publish_time: '2025-08-15T00:00:00Z' },
        { title: 'Go 语言入门教程', url: 'https://example.com/go-tutorial', snippet: '本文从零开始介绍 Go 语言的基础语法、并发编程和标准库使用。', domain: 'example.com', source: 'uapi-searchv1', position: 3, score: 0.75, publish_time: '2025-06-20T00:00:00Z' },
        { title: 'Go 泛型实战：重构遗留代码', url: 'https://example.com/go-generics', snippet: '通过实际案例学习如何利用 Go 泛型重构现有代码，提高代码复用性和类型安全性。', domain: 'example.com', source: 'uapi-searchv1', position: 4, score: 0.71, publish_time: '' },
        { title: '高效 Go 编程：性能优化指南', url: 'https://github.com/go-perf-guide', snippet: '一份全面的 Go 性能优化清单，涵盖内存管理、并发调度和编译器优化技巧。', domain: 'github.com', source: 'uapi-searchv1', position: 5, score: 0.65, publish_time: '2025-12-01T00:00:00Z' },
      ],
      sources: [
        { name: 'uapi-searchv1', status: 'success', result_count: 15, elapsed_ms: 3675, first_result_host: 'go.dev' },
      ],
      process_time_ms: 3675,
      metadata: {
        request_params: { query: 'Go最新的版本是多少', limit: 10, page: 1, timeout_ms: 60000, sort: 'relevance' },
        dedupe_removed: 0,
        rerank_applied: true,
        content_fetched: 0,
      },
    },
  },
  tarot: {
    input: { question: '我最近的事业运如何？', spread_type: 'three' },
    doneOutput: JSON.stringify({ success: true, data: { spread_name: '三牌占卜', cards: [] } }),
    toolData: {
      tool_type: 'tarot',
      question: '我最近的事业运如何？',
      spread_type: 'three',
      spread_name: '三牌占卜',
      cards_count: 3,
      cards: [
        {
          name: '愚人',
          name_en: 'The Fool',
          suit: '大阿尔卡纳',
          element: '风',
          keywords: ['新的开始', '自发行动', '不虑后果'],
          position: '过去',
          status: '正位',
          meaning: ['新的开始', '冒险精神', '无限可能'],
          description: '愚人（正位）— 新的开始，自发行动，不虑后果',
        },
        {
          name: '命运之轮',
          name_en: 'Wheel of Fortune',
          suit: '大阿尔卡纳',
          element: '火',
          keywords: ['转变', '命运', '循环'],
          position: '现在',
          status: '正位',
          meaning: ['好运降临', '命运转折点', '新的机遇'],
          description: '命运之轮（正位）— 转变，命运，循环',
        },
        {
          name: '星星',
          name_en: 'The Star',
          suit: '大阿尔卡纳',
          element: '水',
          keywords: ['希望', '灵感', '平静'],
          position: '未来',
          status: '正位',
          meaning: ['充满希望', '灵感的源泉', '内心的平静'],
          description: '星星（正位）— 希望，灵感，平静',
        },
      ],
    },
  },
  /* ── Todoist 气泡 ── */

  todo_add: {
    input: { content: '复习行波分析', project_name: '学术', section_name: '考试&复习', priority: 3, due_string: 'tomorrow' },
    doneOutput: JSON.stringify({ success: true, data: { task_id: 't_new', content: '复习行波分析', project_name: '学术', section_name: '考试&复习', priority: 3, due: { date: '2026-06-22', string: '2026-06-22 15:00', lang: 'en', is_recurring: false, timezone: null }, duration: { amount: 120, unit: 'minute' }, is_completed: false } }),
    toolData: { task_id: 't_new', content: '复习行波分析', description: '', project_id: 'p2', project_name: '学术', section_id: 's1', section_name: '考试&复习', parent_id: null, labels: [], priority: 3, due: { date: '2026-06-22', string: '2026-06-22 15:00', lang: 'en', is_recurring: false, timezone: null }, deadline: null, duration: { amount: 120, unit: 'minute' }, order: 1, is_collapsed: false, assignee_id: null, assigner_id: null, creator_id: 'u1', is_completed: false, url: null },
  },
  todo_add_quick: {
    input: { text: '买牛奶 #购物 @日用品 明天下午3点 p2' },
    doneOutput: JSON.stringify({ success: true, data: { task_id: 't_quick', content: '买牛奶', project_name: '购物', priority: 2, due: { date: '2026-06-22', string: 'tomorrow at 15:00', lang: 'en', is_recurring: false, timezone: null }, labels: ['日用品'] } }),
    toolData: { task_id: 't_quick', content: '买牛奶', description: '', project_id: 'p5', project_name: '购物', section_id: null, section_name: null, parent_id: null, labels: ['日用品'], priority: 2, due: { date: '2026-06-22', string: 'tomorrow at 15:00', lang: 'en', is_recurring: false, timezone: null }, deadline: null, duration: null, order: 1, is_collapsed: false, assignee_id: null, assigner_id: null, creator_id: 'u1', is_completed: false, url: null },
  },
  todo_list: {
    input: { project_name: '学术', section_name: '考试&复习' },
    doneOutput: JSON.stringify({ success: true, data: { total: 5, tasks: [
      { task_id: 't1', content: 'C++', project_name: '学术', section_name: '考试&复习', priority: 4, due: { date: '2026-07-06', string: '2026-07-06 16:10' }, is_completed: false },
      { task_id: 't2', content: '近现代史', project_name: '学术', section_name: '考试&复习', priority: 2, due: { date: '2026-07-07', string: '2026-07-07 10:40' }, is_completed: false },
      { task_id: 't3', content: '数学分析', project_name: '学术', section_name: '考试&复习', priority: 2, due: { date: '2026-07-08', string: '2026-07-08 08:00' }, is_completed: false },
      { task_id: 't4', content: '复习行波分析', project_name: '学术', section_name: '考试&复习', priority: 3, due: { date: '2026-06-22', string: '2026-06-22 15:00' }, is_completed: false },
      { task_id: 't5', content: '背离散数学公式', project_name: '学术', section_name: '考试&复习', priority: 3, due: { date: '2026-06-22', string: '2026-06-22 20:00' }, is_completed: false },
    ] } }),
    toolData: { total: 5, tasks: [
      { task_id: 't1', content: 'C++', description: '', project_name: '学术', section_name: '考试&复习', priority: 4, due: { date: '2026-07-06', string: '2026-07-06 16:10' }, is_completed: false },
      { task_id: 't2', content: '近现代史', description: '', project_name: '学术', section_name: '考试&复习', priority: 2, due: { date: '2026-07-07', string: '2026-07-07 10:40' }, is_completed: false },
      { task_id: 't3', content: '数学分析', description: '', project_name: '学术', section_name: '考试&复习', priority: 2, due: { date: '2026-07-08', string: '2026-07-08 08:00' }, is_completed: false },
      { task_id: 't4', content: '复习行波分析', description: '', project_name: '学术', section_name: '考试&复习', priority: 3, due: { date: '2026-06-22', string: '2026-06-22 15:00' }, is_completed: false },
      { task_id: 't5', content: '背离散数学公式', description: '', project_name: '学术', section_name: '考试&复习', priority: 3, due: { date: '2026-06-22', string: '2026-06-22 20:00' }, is_completed: false },
    ] },
  },
  todo_complete: {
    input: { task_id: 't5' },
    doneOutput: JSON.stringify({ success: true, data: { task_id: 't5', content: '背离散数学公式', is_completed: true } }),
    toolData: { task_id: 't5', content: '背离散数学公式', description: '', project_id: 'p2', project_name: '学术', section_id: 's1', section_name: '考试&复习', parent_id: null, labels: [], priority: 3, due: { date: '2026-06-22', string: '2026-06-22 20:00', lang: 'en', is_recurring: false, timezone: null }, deadline: null, duration: null, order: 5, is_collapsed: false, assignee_id: null, assigner_id: null, creator_id: 'u1', is_completed: true, url: null },
  },
  todo_uncomplete: {
    input: { task_id: 't5' },
    doneOutput: JSON.stringify({ success: true, data: { task_id: 't5', content: '背离散数学公式', is_completed: false } }),
    toolData: { task_id: 't5', content: '背离散数学公式', description: '', project_id: 'p2', project_name: '学术', section_id: 's1', section_name: '考试&复习', parent_id: null, labels: [], priority: 3, due: { date: '2026-06-22', string: '2026-06-22 20:00', lang: 'en', is_recurring: false, timezone: null }, deadline: null, duration: null, order: 5, is_collapsed: false, assignee_id: null, assigner_id: null, creator_id: 'u1', is_completed: false, url: null },
  },
  todo_delete: {
    input: { task_id: 't5' },
    doneOutput: JSON.stringify({ success: true, data: { task_id: 't5', content: '背离散数学公式' } }),
    toolData: { task_id: 't5', content: '背离散数学公式', description: '', project_id: 'p2', project_name: '学术', section_id: 's1', section_name: '考试&复习', parent_id: null, labels: [], priority: 3, due: { date: '2026-06-22', string: '2026-06-22 20:00', lang: 'en', is_recurring: false, timezone: null }, deadline: null, duration: null, order: 5, is_collapsed: false, assignee_id: null, assigner_id: null, creator_id: 'u1', is_completed: false, url: null },
  },
  todo_update: {
    input: { task_id: 't2', description: '中国近现代史纲要，7月7日10:40考试，沙河校区' },
    doneOutput: JSON.stringify({ success: true, data: { task_id: 't2', content: '近现代史', description: '中国近现代史纲要，7月7日10:40考试，沙河校区' } }),
    toolData: { task_id: 't2', content: '近现代史', description: '中国近现代史纲要，7月7日10:40考试，沙河校区', project_id: 'p2', project_name: '学术', section_id: 's1', section_name: '考试&复习', labels: [], priority: 2, due: { date: '2026-07-07', string: '2026-07-07 10:40' }, is_completed: false },
  },
  todo_query: {
    input: { task_id: 't4' },
    doneOutput: JSON.stringify({ success: true, data: { task_id: 't4', content: '复习行波分析', description: '半波损失、驻波叠加、两端反射分析，结合 Sonetto 生成的复习资料', project_name: '学术', section_name: '考试&复习', priority: 3, due: { date: '2026-06-22', string: '2026-06-22 15:00' }, creator_id: '58490144', is_completed: false } }),
    toolData: { task_id: 't4', content: '复习行波分析', description: '半波损失、驻波叠加、两端反射分析，结合 Sonetto 生成的复习资料', project_id: 'p2', project_name: '学术', section_id: 's1', section_name: '考试&复习', parent_id: null, labels: [], priority: 3, due: { date: '2026-06-22', string: '2026-06-22 15:00', lang: 'en', is_recurring: false, timezone: null }, deadline: null, duration: null, order: 4, is_collapsed: false, assignee_id: null, assigner_id: null, creator_id: '58490144', is_completed: false, url: null },
  },
  todo_list_projects: {
    input: {},
    doneOutput: JSON.stringify({ success: true, data: { total: 4, projects: [
      { project_id: 'p_inbox', name: 'Inbox', color: 'grey', is_inbox_project: true, view_style: 'list' },
      { project_id: 'p2', name: '学术', color: 'blue', is_inbox_project: false, view_style: 'board' },
      { project_id: 'p3', name: '医疗', color: 'green', is_inbox_project: false, view_style: 'list' },
      { project_id: 'p4', name: '校园', color: 'taupe', is_inbox_project: false, view_style: 'list' },
    ] } }),
    toolData: { total: 4, projects: [
      { project_id: 'p_inbox', name: 'Inbox', color: 'grey', description: '', order: 1, is_favorite: false, is_archived: false, is_shared: false, is_collapsed: false, parent_id: null, view_style: 'list', can_assign_tasks: false, is_inbox_project: true, workspace_id: 'w1', folder_id: null },
      { project_id: 'p2', name: '学术', color: 'blue', description: '', order: 2, is_favorite: true, is_archived: false, is_shared: false, is_collapsed: false, parent_id: null, view_style: 'board', can_assign_tasks: false, is_inbox_project: false, workspace_id: 'w1', folder_id: null },
      { project_id: 'p3', name: '医疗', color: 'green', description: '', order: 3, is_favorite: false, is_archived: false, is_shared: false, is_collapsed: false, parent_id: null, view_style: 'list', can_assign_tasks: false, is_inbox_project: false, workspace_id: 'w1', folder_id: null },
      { project_id: 'p4', name: '校园', color: 'taupe', description: '', order: 4, is_favorite: false, is_archived: false, is_shared: false, is_collapsed: false, parent_id: null, view_style: 'list', can_assign_tasks: false, is_inbox_project: false, workspace_id: 'w1', folder_id: null },
    ] },
  },
  todo_list_sections: {
    input: { project_name: '学术' },
    doneOutput: JSON.stringify({ success: true, data: { total: 3, sections: [
      { section_id: 's1', name: '作业', project_id: 'p2', project_name: '学术', order: 1, is_collapsed: false },
      { section_id: 's2', name: '考试&复习', project_id: 'p2', project_name: '学术', order: 2, is_collapsed: false },
      { section_id: 's3', name: '杂项', project_id: 'p2', project_name: '学术', order: 3, is_collapsed: false },
    ] } }),
    toolData: { total: 3, project_name: '学术', sections: [
      { section_id: 's1', name: '作业', project_id: 'p2', project_name: '学术', order: 1, is_collapsed: false },
      { section_id: 's2', name: '考试&复习', project_id: 'p2', project_name: '学术', order: 2, is_collapsed: false },
      { section_id: 's3', name: '杂项', project_id: 'p2', project_name: '学术', order: 3, is_collapsed: false },
    ] },
  },
  todo_list_labels: {
    input: {},
    doneOutput: JSON.stringify({ success: true, data: { total: 0, labels: [] } }),
    toolData: { total: 0, labels: [] },
  },
  task_tracker: {
    input: { tasks: ['分析需求文档', '设计数据库结构', '编写API接口', '前端页面开发', '集成测试'] },
    doneOutput: JSON.stringify({
      success: true,
      data: {
        status: 'in_progress',
        total_steps: 5,
        current_step: 2,
        current_task: '设计数据库结构',
        tasks: ['分析需求文档', '设计数据库结构', '编写API接口', '前端页面开发', '集成测试'],
      },
    }),
    toolData: {
      tool_type: 'task_tracker',
      status: 'in_progress',
      total_steps: 5,
      current_step: 2,
      current_task: '设计数据库结构',
      tasks: ['分析需求文档', '设计数据库结构', '编写API接口', '前端页面开发', '集成测试'],
    },
  },
  run_python: {
    input: {
      code: 'import json\nfrom pathlib import Path\n\ndata = {"name": "岚山", "visitors": 1200}\nprint(f"地点: {data[\'name\']}")\nprint(f"游客数: {data[\'visitors\']}")\n\n# 写入文件\npath = Path("/tmp/report.json")\npath.write_text(json.dumps(data, ensure_ascii=False, indent=2))\nprint(f"报告已保存至 {path}")',
    },
    doneOutput: JSON.stringify({
      success: true,
      data: { output: '地点: 岚山\n游客数: 1200\n报告已保存至 /tmp/report.json' },
    }),
    toolData: {
      tool_type: 'run_python',
      stdout: '地点: 岚山\n游客数: 1200\n报告已保存至 /tmp/report.json',
      code: 'import json\nfrom pathlib import Path\n\ndata = {"name": "岚山", "visitors": 1200}\nprint(f"地点: {data[\'name\']}")\nprint(f"游客数: {data[\'visitors\']}")\n\n# 写入文件\npath = Path("/tmp/report.json")\npath.write_text(json.dumps(data, ensure_ascii=False, indent=2))\nprint(f"报告已保存至 {path}")',
    },
  },
  file_read: {
    input: { file_path: 'src/config/app.config.json' },
    doneOutput: JSON.stringify({ success: true, data: { content: '...' } }),
    toolData: {
      operation: 'read_file',
      file_path: '/home/user/project/src/config/app.config.json',
      file_name: 'app.config.json',
      encoding: 'UTF-8',
      size_bytes: 2841,
      line_count: 68,
      content: `{\n  "app_name": "SonettoHere",\n  "version": "2.1.0",\n  "description": "AI 聊天应用",\n  "theme": "dark",\n  "locale": "zh-CN",\n  "features": {\n    "kaleidoscope": true,\n    "playground": true,\n    "voice_input": false,\n    "export_chat": true\n  },\n  "editor": {\n    "font_size": 14,\n    "tab_size": 2,\n    "word_wrap": true,\n    "minimap": false\n  },\n  "shortcuts": {\n    "send_message": "Ctrl+Enter",\n    "new_chat": "Ctrl+Shift+N",\n    "toggle_sidebar": "Ctrl+B"\n  }\n}`,
    },
  },
  file_write: {
    input: { file_path: 'output/report.md', content: '# 项目报告\n\n## 概览\n...' },
    doneOutput: JSON.stringify({ success: true, data: { message: '文件写入成功', file_path: 'output/report.md' } }),
    toolData: {
      operation: 'write_file',
      file_path: '/home/user/project/output/report.md',
      file_name: 'report.md',
      size_bytes: 3840,
      line_count: 95,
      success: true,
    },
  },
  file_list: {
    input: { directory_path: 'src/components/', file_filter: '*.vue' },
    doneOutput: JSON.stringify({ success: true, data: { files: [], total: 12 } }),
    toolData: {
      operation: 'list_directory',
      directory_path: '/home/user/project/src/components/',
      total_items: 12,
      items: [
        { name: 'ChatWindow.vue', type: 'file', size_bytes: 8520, modified: '05-12' },
        { name: 'MessageBubble.vue', type: 'file', size_bytes: 6240, modified: '05-11' },
        { name: 'ToolCallCard.vue', type: 'file', size_bytes: 15380, modified: '05-10' },
        { name: 'ToolBubbleRouter.vue', type: 'file', size_bytes: 1240, modified: '05-15' },
        { name: 'ThinkingBlock.vue', type: 'file', size_bytes: 3820, modified: '05-09' },
        { name: 'tools/', type: 'directory', modified: '05-15' },
        { name: 'HelloWorld.vue', type: 'file', size_bytes: 560, modified: '04-28' },
        { name: 'icons/', type: 'directory', modified: '05-01' },
        { name: 'App.vue', type: 'file', size_bytes: 2890, modified: '05-08' },
        { name: 'BaseCard.vue', type: 'file', size_bytes: 2100, modified: '04-25' },
      ],
    },
  },
  file_operations: {
    input: { operation: 'list_directory', directory_path: 'src/components/', file_filter: '*.vue' },
    doneOutput: JSON.stringify({ success: true, data: { directory: '/home/user/project/src/components/', items: [], count: 12 } }),
    toolData: {
      operation: 'list_directory',
      directory_path: '/home/user/project/src/components/',
      total_items: 12,
      items: [
        { name: 'ChatWindow.vue', type: 'file', size_bytes: 8520, modified: '05-12' },
        { name: 'MessageBubble.vue', type: 'file', size_bytes: 6240, modified: '05-11' },
        { name: 'ToolCallCard.vue', type: 'file', size_bytes: 15380, modified: '05-10' },
        { name: 'ToolBubbleRouter.vue', type: 'file', size_bytes: 1240, modified: '05-15' },
        { name: 'ThinkingBlock.vue', type: 'file', size_bytes: 3820, modified: '05-09' },
        { name: 'tools/', type: 'directory', modified: '05-15' },
        { name: 'HelloWorld.vue', type: 'file', size_bytes: 560, modified: '04-28' },
        { name: 'icons/', type: 'directory', modified: '05-01' },
        { name: 'App.vue', type: 'file', size_bytes: 2890, modified: '05-08' },
        { name: 'BaseCard.vue', type: 'file', size_bytes: 2100, modified: '04-25' },
      ],
    },
  },
  analyze_image: {
    input: { image_source: 'url:https://example.com/photo.jpg', prompt: '请描述这张图片' },
    doneOutput: JSON.stringify({
      success: true,
      data: { response: '这张图片展示了一片宁静的竹林小径，阳光透过竹叶洒落在地面上形成斑驳的光影。小径蜿蜒伸向远方，两旁是高耸的翠竹。画面整体色调清新自然，给人一种幽静深远的感觉，仿佛置身于京都岚山的竹林之中。' },
    }),
    toolData: {
      tool_type: 'analyze_image',
      response: '这张图片展示了一片宁静的竹林小径，阳光透过竹叶洒落在地面上形成斑驳的光影。小径蜿蜒伸向远方，两旁是高耸的翠竹。画面整体色调清新自然，给人一种幽静深远的感觉，仿佛置身于京都岚山的竹林之中。',
    },
  },
  tavily_extract: {
    input: { url: 'https://example.com/article', wait_ms: 5000 },
    doneOutput: JSON.stringify({
      success: true,
      data: {
        url: 'https://example.com/article',
        title: 'Example Article — A Sample Page for Web Scraping',
        content: '<article><h1>Example Article</h1><p>This is a sample article page used for testing the web scraping tool. It contains various HTML elements including headings, paragraphs, links, and images.</p><p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.</p><p>Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.</p></article>',
        open_graph: { title: 'Example Article', description: 'A sample page for testing web scraping functionality.', image: 'https://example.com/og-image.jpg', type: 'article' },
        headings: [{ level: 1, text: 'Example Article' }, { level: 2, text: 'Introduction' }, { level: 2, text: 'Methodology' }, { level: 3, text: 'Data Collection' }, { level: 3, text: 'Analysis' }, { level: 2, text: 'Results' }],
        links: [{ text: 'About Us', href: 'https://example.com/about' }, { text: 'Contact', href: 'https://example.com/contact' }, { text: 'Privacy Policy', href: 'https://example.com/privacy' }, { text: 'Learn More', href: 'https://example.com/learn' }],
        images: [{ src: 'https://example.com/photo1.jpg', alt: 'Sample image 1' }, { src: 'https://example.com/photo2.jpg', alt: 'Sample image 2' }],
      },
    }),
    toolData: {
      url: 'https://example.com/article',
      title: 'Example Article — A Sample Page for Web Scraping',
      content: '<article><h1>Example Article</h1><p>This is a sample article page used for testing the web scraping tool. It contains various HTML elements including headings, paragraphs, links, and images.</p><p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.</p><p>Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.</p></article>',
      open_graph: { title: 'Example Article', description: 'A sample page for testing web scraping functionality.', image: 'https://example.com/og-image.jpg', type: 'article' },
      headings: [{ level: 1, text: 'Example Article' }, { level: 2, text: 'Introduction' }, { level: 2, text: 'Methodology' }, { level: 3, text: 'Data Collection' }, { level: 3, text: 'Analysis' }, { level: 2, text: 'Results' }],
      links: [{ text: 'About Us', href: 'https://example.com/about' }, { text: 'Contact', href: 'https://example.com/contact' }, { text: 'Privacy Policy', href: 'https://example.com/privacy' }, { text: 'Learn More', href: 'https://example.com/learn' }],
      images: [{ src: 'https://example.com/photo1.jpg', alt: 'Sample image 1' }, { src: 'https://example.com/photo2.jpg', alt: 'Sample image 2' }],
    },
  },
}

function buildMock(name: string, status: ToolStatus): ToolCall {
  const tpl = mockTemplates[name]
  const input = tpl
    ? JSON.stringify(tpl.input, null, 2)
    : JSON.stringify({ example_param: '示例参数' }, null, 2)

  const base: ToolCall = {
    kind: 'tool',
    name,
    input,
    output: null,
    elapsed: null,
    status,
  }

  if (status === 'running') {
    return { ...base, elapsed: null, output: null }
  }

  if (status === 'error') {
    return { ...base, elapsed: 1.23, output: 'Error: 请求超时，请检查网络连接后重试' }
  }

  // done
  return {
    ...base,
    elapsed: name === 'tavily_search' ? 1.82 : name === 'tavily_extract' ? 2.64 : 2.35,
    output: tpl?.doneOutput ?? JSON.stringify({ success: true, data: { result: 'OK' } }),
    toolData: tpl?.toolData,
  }
}

// ── 交互日志 ──
interface LogEntry {
  time: string
  action: string
  data?: string
}

const actionLog = ref<LogEntry[]>([])

function logAction(payload: { action: string; data?: unknown }) {
  const now = new Date()
  const time = now.toLocaleTimeString('zh-CN', { hour12: false })
  actionLog.value.unshift({
    time,
    action: payload.action,
    data: payload.data ? JSON.stringify(payload.data, null, 2) : undefined,
  })
  if (actionLog.value.length > 50) {
    actionLog.value.pop()
  }
}
</script>

<style scoped>
.playground {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--bg-primary);
}

/* ── Header ── */
.pg-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 24px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-card);
  flex-shrink: 0;
}

.pg-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.pg-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.pg-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 100px;
  background: #fef3c7;
  color: #d97706;
  font-weight: 600;
}

.pg-stats {
  font-size: 13px;
  color: var(--text-secondary);
}

/* ── Body ── */
.pg-body {
  flex: 1;
  display: flex;
  min-height: 0;
}

/* ── Sidebar ── */
.pg-sidebar {
  width: 220px;
  min-width: 220px;
  border-right: 1px solid var(--border);
  background: var(--bg-secondary);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.pg-section-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.pg-sidebar .pg-section-title {
  padding: 16px 16px 10px;
}

.tool-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 10px 12px;
}

.tool-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.12s;
  font-size: 13px;
}

.tool-item:hover {
  background: var(--bg-card);
}

.tool-item.active {
  background: var(--bg-card);
  box-shadow: var(--shadow);
}

.tool-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--border);
  flex-shrink: 0;
}

.tool-dot.registered {
  background: var(--accent);
}

.tool-item-name {
  color: var(--text-primary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-item-id {
  font-size: 10px;
  color: var(--text-secondary);
  font-family: 'SF Mono', 'Consolas', monospace;
  display: none;
}

.chip {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 100px;
  font-weight: 600;
  flex-shrink: 0;
}

.chip.registered {
  background: #dcfce7;
  color: #166534;
}

.chip.fallback {
  background: #f3f4f6;
  color: #6b7280;
}

/* ── Main ── */
.pg-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.state-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-card);
  flex-shrink: 0;
}

.state-bar-label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-right: 4px;
}

.state-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 14px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-primary);
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
  font-family: inherit;
}

.state-btn:hover {
  border-color: var(--accent-light);
  color: var(--text-primary);
}

.state-btn.active {
  border-color: var(--accent);
  color: var(--accent);
  background: #eff6ff;
  font-weight: 600;
}

.state-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--border);
}

.state-dot.running {
  background: var(--accent);
  animation: pulse 1.2s ease-in-out infinite;
}

.state-dot.done {
  background: var(--status-ok);
}

.state-dot.error {
  background: var(--status-error);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

/* ── Preview ── */
.preview-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.preview-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.preview-tool-id {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 11px;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  padding: 2px 6px;
  border-radius: 4px;
}

.preview-using {
  font-size: 12px;
  color: var(--accent);
}

.preview-using.fallback-text {
  color: var(--text-secondary);
}

.preview-body {
  max-width: 600px;
}

/* ── Action Log ── */
.action-log {
  border-top: 1px solid var(--border);
  background: var(--bg-card);
  flex-shrink: 0;
  max-height: 160px;
  display: flex;
  flex-direction: column;
}

.action-log-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px 8px;
}

.clear-btn {
  font-size: 12px;
  color: var(--text-secondary);
  background: none;
  border: none;
  cursor: pointer;
  font-family: inherit;
}

.clear-btn:hover {
  color: var(--text-primary);
}

.log-entries {
  flex: 1;
  overflow-y: auto;
  padding: 0 24px 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.log-entry {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 12px;
  font-family: 'SF Mono', 'Consolas', monospace;
  line-height: 1.6;
}

.log-idx {
  color: var(--border);
  flex-shrink: 0;
  min-width: 24px;
}

.log-time {
  color: var(--text-secondary);
  flex-shrink: 0;
}

.log-action {
  color: var(--accent);
  font-weight: 600;
}

.log-data {
  color: var(--text-secondary);
  font-size: 11px;
  white-space: pre;
  overflow: hidden;
  text-overflow: ellipsis;
}

.log-empty {
  font-size: 12px;
  color: var(--text-secondary);
  font-style: italic;
  padding: 4px 0;
}
</style>
