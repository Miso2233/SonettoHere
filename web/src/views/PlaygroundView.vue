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
    'bilibili_download': 'BilibiliDownloadBubble.vue',
    'todo_add': 'TodoBubble.vue',
    'todo_list': 'TodoBubble.vue',
    'todo_complete': 'TodoBubble.vue',
    'todo_uncomplete': 'TodoBubble.vue',
    'todo_delete': 'TodoBubble.vue',
    'todo_update': 'TodoBubble.vue',
    'todo_query': 'TodoBubble.vue',
    'todo_list_projects': 'TodoBubble.vue',
    'task_tracker': 'TaskTrackerBubble.vue',
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
  bilibili_download: {
    input: {
      url: 'https://www.bilibili.com/video/BV1xx411c7mD',
      quality: 'highest',
    },
    doneOutput: '下载完成',
    toolData: {
      video_title: '【4K 60FPS】京都·红叶季 — 岚山竹林与常寂光寺',
      cover_url: 'https://i0.hdslb.com/bfs/archive/82501cb151d19a4b17f8c3b3cd6c5e4e6c8a7b9d.jpg',
      file_path: 'output/bilibili/京都红叶季_4K60FPS.mp4',
      quality: '超清 4K',
      filesize_mb: 847.3,
      duration: '12:48',
    },
  },
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
        forecast: [
          { day: '今天', high: '25°C', low: '18°C', condition: '晴转多云' },
          { day: '明天', high: '27°C', low: '19°C', condition: '晴' },
          { day: '后天', high: '23°C', low: '17°C', condition: '小雨' },
        ],
      },
    }),
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
  search: {
    input: { query: '京都红叶最佳观赏时间' },
    doneOutput: '京都红叶最佳观赏期为**11月中旬至12月上旬**。\n\n推荐地点：\n- 岚山（竹林+红叶）\n- 永观堂（夜枫名所）\n- 东福寺（通天桥）\n- 清水寺（夜间特别参拜）',
  },
  tarot: {
    input: { question: '今天适合开始新项目吗？', spread: 'single' },
    doneOutput: JSON.stringify({
      success: true,
      data: {
        card_name: 'The Fool · 愚者',
        card_meaning: '新的开始、冒险、天真',
        interpretation: '这张牌暗示现在是踏上新征程的好时机。保持开放的心态，勇敢迈出第一步。',
      },
    }),
  },
  todo_add: {
    input: { content: '在岚山竹林拍一张全景照', project_name: '旅行计划', priority: 3 },
    doneOutput: JSON.stringify({
      success: true,
      data: { task_id: '12345678', content: '在岚山竹林拍一张全景照', due_date: '2026-05-20', priority: 3, project: '旅行计划' },
    }),
    toolData: {
      tool_type: 'single_task',
      task_id: '12345678',
      content: '在岚山竹林拍一张全景照',
      due_date: '2026-05-20',
      priority: 3,
      project: '旅行计划',
    },
  },
  todo_list: {
    input: {},
    doneOutput: JSON.stringify({
      success: true,
      data: {
        total: 4,
        tasks: [
          { task_id: '111', content: '预订京都酒店', due_date: '2026-05-25', priority: 4, project: '旅行计划', is_completed: false },
          { task_id: '222', content: '整理岚山攻略', due_date: '2026-05-18', priority: 2, project: '旅行计划', is_completed: false },
          { task_id: '333', content: '写周报', due_date: '2026-05-16', priority: 1, project: '工作', is_completed: true },
          { task_id: '444', content: '买机票', due_date: null, priority: 3, project: '旅行计划', is_completed: false },
        ],
      },
    }),
    toolData: {
      tool_type: 'task_list',
      total: 4,
      tasks: [
        { task_id: '111', content: '预订京都酒店', due_date: '2026-05-25', priority: 4, project: '旅行计划', is_completed: false },
        { task_id: '222', content: '整理岚山攻略', due_date: '2026-05-18', priority: 2, project: '旅行计划', is_completed: false },
        { task_id: '333', content: '写周报', due_date: '2026-05-16', priority: 1, project: '工作', is_completed: true },
        { task_id: '444', content: '买机票', due_date: null, priority: 3, project: '旅行计划', is_completed: false },
      ],
    },
  },
  todo_complete: {
    input: { task_id: '111' },
    doneOutput: JSON.stringify({
      success: true,
      data: { task_id: '111', message: '任务已标记为完成' },
    }),
    toolData: {
      tool_type: 'single_task',
      task_id: '111',
      content: '预订京都酒店',
      message: '任务已标记为完成',
    },
  },
  todo_uncomplete: {
    input: { task_id: '111' },
    doneOutput: JSON.stringify({
      success: true,
      data: { task_id: '111', message: '任务已重新打开' },
    }),
    toolData: {
      tool_type: 'single_task',
      task_id: '111',
      content: '预订京都酒店',
      message: '任务已重新打开',
    },
  },
  todo_delete: {
    input: { task_id: '222' },
    doneOutput: JSON.stringify({
      success: true,
      data: { task_id: '222', message: '任务删除成功' },
    }),
    toolData: {
      tool_type: 'single_task',
      task_id: '222',
      content: '整理岚山攻略',
      message: '任务删除成功',
    },
  },
  todo_update: {
    input: { task_id: '333', content: '写双周报', priority: 2 },
    doneOutput: JSON.stringify({
      success: true,
      data: { task_id: '333', content: '写双周报', due_date: '2026-05-20', priority: 2, project: '工作' },
    }),
    toolData: {
      tool_type: 'single_task',
      task_id: '333',
      content: '写双周报',
      due_date: '2026-05-20',
      priority: 2,
      project: '工作',
    },
  },
  todo_query: {
    input: { task_id: '444' },
    doneOutput: JSON.stringify({
      success: true,
      data: { task_id: '444', content: '买机票', due_date: null, priority: 3, project: '旅行计划', is_completed: false },
    }),
    toolData: {
      tool_type: 'single_task',
      task_id: '444',
      content: '买机票',
      due_date: null,
      priority: 3,
      project: '旅行计划',
      is_completed: false,
    },
  },
  todo_list_projects: {
    input: {},
    doneOutput: JSON.stringify({
      success: true,
      data: {
        total: 3,
        projects: [
          { project_id: '23456789', name: '旅行计划' },
          { project_id: '34567890', name: '工作' },
          { project_id: '45678901', name: 'Inbox' },
        ],
      },
    }),
    toolData: {
      tool_type: 'project_list',
      total: 3,
      projects: [
        { project_id: '23456789', name: '旅行计划' },
        { project_id: '34567890', name: '工作' },
        { project_id: '45678901', name: 'Inbox' },
      ],
    },
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
    elapsed: name === 'bilibili_download' ? 18.45 : (name === 'search' ? 1.82 : 2.35),
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
  color: #92400e;
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
  background: #d4e5d4;
  color: #2d5a2d;
}

.chip.fallback {
  background: #e5ddd2;
  color: #6b5e4e;
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
  background: #fdf8f2;
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
  background: #5a9e5a;
}

.state-dot.error {
  background: #c05050;
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
