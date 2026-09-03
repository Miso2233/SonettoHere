<template>
  <div
    class="bg-tracker-bar"
    :class="{ idle: !hasData, 'has-data': hasData }"
    @mouseenter="showMenu = true"
    @mouseleave="showMenu = false"
  >
    <template v-if="!hasData">
      <span class="bar-label">无后台任务</span>
    </template>

    <template v-else>
      <span class="bar-progress-text">
        <span class="bar-num-done">{{ doneCount }}</span>
        /<span class="bar-num-total">{{ totalCount }}</span>
      </span>

      <span class="bar-sep">·</span>
      <span class="bar-status-label">{{ statusLabel }}</span>

      <span class="bar-progress-track">
        <span class="bar-progress-fill" :style="{ width: progressPercent + '%' }"></span>
      </span>
    </template>

    <!-- 悬停菜单：后台任务明细 -->
    <Transition name="menu-fade">
      <div v-if="showMenu && hasData" class="hover-menu" @mouseenter="showMenu = true" @mouseleave="showMenu = false">
        <div class="menu-header">
          <span>后台任务 · {{ totalCount }} 项</span>
        </div>
        <div class="menu-list">
          <div
            v-for="t in sortedTasks"
            :key="t.index"
            class="menu-row"
            :class="'row-' + t.status"
          >
            <span class="menu-index">#{{ t.index }}</span>
            <span class="menu-icon" :class="'icon-' + t.status">
              <template v-if="t.status === 'completed'">✓</template>
              <template v-else-if="t.status === 'failed'">✗</template>
              <template v-else>●</template>
            </span>
            <span class="menu-content">{{ toolDisplayName(t.toolName) }}</span>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { toolDisplayName } from '@/components/tools/_shared/displayNames'

export interface BackgroundTrackerTask {
  index: number
  toolName: string
  status: 'running' | 'completed' | 'failed'
}

const props = defineProps<{ data: BackgroundTrackerTask[] | null }>()

const showMenu = ref(false)

const tasks = computed(() => props.data ?? [])
const totalCount = computed(() => tasks.value.length)
const doneCount = computed(
  () => tasks.value.filter(t => t.status === 'completed' || t.status === 'failed').length
)
const runningCount = computed(
  () => tasks.value.filter(t => t.status === 'running').length
)

const sortedTasks = computed(() => [...tasks.value].sort((a, b) => b.index - a.index))

const progressPercent = computed(() => {
  if (totalCount.value <= 0) return 0
  return Math.round((doneCount.value / totalCount.value) * 100)
})

const statusLabel = computed(() => {
  if (totalCount.value === 0) return ''
  if (runningCount.value > 0) return `运行中 ${runningCount.value}`
  return '已结束'
})

const hasData = computed(() => totalCount.value > 0)
</script>

<style scoped>
/* 与 TaskTrackerBar 完全一致的结构与色板（黑白灰 + 进度条） */
.bg-tracker-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  font-size: 12px;
  user-select: none;
  flex-shrink: 0;
  border: 1.5px solid #0000001e;
  border-radius: 6px;
  padding: 4px 12px;
  box-shadow: var(--shadow-xs);
  transition: opacity 0.25s;
}

.bg-tracker-bar.idle {
  opacity: 0.35;
}

.bg-tracker-bar.has-data {
  position: relative;
}

.bar-label {
  font-weight: 600;
  color: #999;
}

.bar-progress-text {
  font-variant-numeric: tabular-nums;
  color: #666;
}

.bar-num-done {
  font-weight: 700;
  color: #000;
}

.bar-num-total {
  color: #999;
}

.bar-sep {
  color: #ccc;
}

.bar-status-label {
  color: #000;
  font-weight: 600;
}

.bar-progress-track {
  width: 60px;
  height: 6px;
  background: #d0d0d0;
  border-radius: 3px;
  overflow: hidden;
  flex-shrink: 0;
  display: flex;
}

.bar-progress-fill {
  height: 100%;
  min-width: 8px;
  background: #000;
  border-radius: 3px;
  transition: width 0.3s ease;
}

/* ── 悬停菜单 ── */
.hover-menu {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  min-width: 220px;
  max-width: 360px;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.10), 0 1px 4px rgba(0,0,0,0.06);
  z-index: 500;
  overflow: hidden;
}

.menu-header {
  padding: 10px 12px 8px;
  font-size: 11px;
  font-weight: 600;
  color: #999;
  border-bottom: 1px solid #f0f0f0;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.menu-list {
  max-height: 260px;
  overflow-y: auto;
}

.menu-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  font-size: 12px;
  line-height: 1.5;
  border-bottom: 1px solid #f5f5f5;
  transition: background 0.1s;
}

.menu-row:last-child {
  border-bottom: none;
}

.menu-row:hover {
  background: #f9f9f9;
}

.menu-index {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 11px;
  font-weight: 700;
  color: #000;
  flex-shrink: 0;
  width: 26px;
}

.menu-icon {
  width: 14px;
  text-align: center;
  font-size: 12px;
  flex-shrink: 0;
}

.menu-icon.icon-completed {
  color: #999;
}

.menu-icon.icon-running {
  color: #000;
  font-weight: 700;
  animation: bg-tracker-pulse 1.4s ease-in-out infinite;
}

.menu-icon.icon-failed {
  color: #b91c1c;
  font-weight: 700;
}

.row-running .menu-content {
  color: #000;
  font-weight: 600;
}

.row-completed .menu-content {
  color: #999;
}

.row-failed .menu-content {
  color: #b91c1c;
}

@keyframes bg-tracker-pulse {
  0%, 100% { opacity: 0.35; }
  50% { opacity: 1; }
}

.menu-fade-enter-active,
.menu-fade-leave-active {
  transition: opacity 0.15s ease, transform 0.12s ease;
}

.menu-fade-enter-from,
.menu-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
