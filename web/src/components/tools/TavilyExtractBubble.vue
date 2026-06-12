<template>
  <BubbleChrome :tool-call="toolCall">
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>正在提取内容...</span>
    </div>

    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '提取失败' }}
    </div>

    <template v-else-if="toolCall.status === 'done'">
      <div v-if="hasData" class="te">
        <div class="te-bar">
          <span>提取 {{ ok }} 个页面 · {{ responseTime }}ms</span>
          <span v-if="failCount" class="te-badge">{{ failCount }} 个失败</span>
        </div>

        <div v-if="pages.length" class="te-tabs">
          <button v-for="(p, i) in pages" :key="i" class="te-tab" :class="{ active: tab === i }" @click="tab = i">
            {{ p.title || p.url.slice(0, 28) + '…' }}
          </button>
        </div>

        <div v-if="page" class="te-card">
          <div class="te-card-head">
            <a class="te-card-title" :href="page.url" target="_blank" rel="noopener noreferrer" @click.prevent="openUrl(page.url)">{{ page.title || page.url }}</a>
            <div class="te-card-url">{{ page.url }}</div>
          </div>

          <div v-if="page.images?.length" class="te-imgs">
            <div class="te-label">图片（{{ page.images.length }}）</div>
            <div class="te-imgs-list">
              <img v-for="(img, j) in page.images" :key="j" :src="img" class="te-thumb" alt="" @click="openUrl(img)" />
            </div>
          </div>

          <div v-if="page.raw_content" class="te-body-wrap">
            <div class="te-body-head">
              <span class="te-label">正文</span>
              <button class="te-btn" @click="expand = !expand">{{ expand ? '− 收起' : '+ 展开全部' }}</button>
            </div>
            <div class="te-body" :class="{ folded: !expand }">{{ page.raw_content }}</div>
          </div>

          <div v-else class="te-none">无正文内容</div>
        </div>

        <div v-if="fails.length" class="te-fails">
          <div class="te-label">失败页面</div>
          <div v-for="(f, i) in fails" :key="i" class="te-fail-item">
            <span class="te-fail-url">{{ f.url }}</span>
            <span v-if="f.error" class="te-fail-msg">{{ f.error }}</span>
          </div>
        </div>
      </div>

      <div v-else class="raw-output">{{ fallback }}</div>
    </template>
  </BubbleChrome>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ToolCall } from '@/types'
import BubbleChrome from './_shared/BubbleChrome.vue'

const props = defineProps<{ toolCall: ToolCall }>()
const emit = defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

const tab = ref(0)
const expand = ref(false)

const td = computed<Record<string, any>>(() => {
  if (props.toolCall.toolData) return props.toolCall.toolData as Record<string, any>
  if (props.toolCall.output) {
    try { const p = JSON.parse(props.toolCall.output); if (p?.data) return p.data as Record<string, any> } catch { /* */ }
  }
  return {}
})

const hasData = computed(() => Object.keys(td.value).length > 0)
const responseTime = computed(() => td.value.response_time ?? 0)

const pages = computed<Array<Record<string, any>>>(() => Array.isArray(td.value.results) ? td.value.results : [])
const ok = computed(() => pages.value.length)

const fails = computed<Array<Record<string, any>>>(() => Array.isArray(td.value.failed_results) ? td.value.failed_results : [])
const failCount = computed(() => fails.value.length)

const page = computed(() => pages.value[tab.value] ?? null)

function openUrl(url: string) {
  emit('action', { action: 'open_url', data: { url } })
  window.open(url, '_blank', 'noopener,noreferrer')
}

const fallback = computed(() => props.toolCall.output
  ? (props.toolCall.output.length > 500 ? props.toolCall.output.slice(0, 500) + '…' : props.toolCall.output)
  : null)
</script>

<style scoped>
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

.te {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 4px 0;
}

/* ── 概览栏 ── */
.te-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: #f5f5f5;
  border-radius: 6px;
  font-size: 12px;
  color: #333;
}
.te-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border: 1px solid #bbb;
  border-radius: 2px;
  color: #666;
}

/* ── Tab ── */
.te-tabs {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.te-tab {
  font-size: 11px;
  padding: 4px 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #fff;
  color: #555;
  cursor: pointer;
  transition: all .15s;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.te-tab:hover { border-color: #888; }
.te-tab.active { background: #222; color: #fff; border-color: #222; }

/* ── 卡片 ── */
.te-card {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  padding: 12px;
}
.te-card-head {
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid #eee;
}
.te-card-title {
  font-size: 15px;
  font-weight: 600;
  color: #000;
  cursor: pointer;
  text-decoration: none;
  display: block;
  line-height: 1.4;
}
.te-card-title:hover { text-decoration: underline; }
.te-card-url {
  font-size: 11px;
  color: #888;
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── 标签 -- */
.te-label {
  font-size: 11px;
  font-weight: 700;
  color: #666;
  letter-spacing: .5px;
  text-transform: uppercase;
  margin-bottom: 6px;
}

/* ── 图片 ── */
.te-imgs {
  margin-bottom: 10px;
}
.te-imgs-list {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.te-thumb {
  width: 80px;
  height: 60px;
  object-fit: cover;
  border-radius: 4px;
  border: 1px solid #ddd;
  cursor: pointer;
  transition: opacity .15s;
}
.te-thumb:hover { opacity: .7; }

/* ── 正文 ── */
.te-body-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.te-body-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.te-btn {
  font-size: 11px;
  color: #555;
  background: none;
  border: 1px solid #ccc;
  border-radius: 3px;
  padding: 2px 8px;
  cursor: pointer;
  transition: background .15s;
}
.te-btn:hover { background: #eee; }

.te-body {
  font-size: 12px;
  line-height: 1.8;
  color: #333;
  white-space: pre-wrap;
  word-break: break-word;
}
.te-body.folded {
  max-height: 280px;
  overflow: hidden;
  position: relative;
}
.te-body.folded::after {
  content: '';
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 60px;
  background: linear-gradient(transparent, #fff);
  pointer-events: none;
}

.te-none {
  font-size: 13px;
  color: #999;
  text-align: center;
  padding: 24px;
}

/* ── 失败列表 ── */
.te-fails {
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  padding: 10px 12px;
  background: #fafafa;
}
.te-fail-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 5px 0;
  font-size: 12px;
  border-top: 1px solid #eee;
}
.te-fail-item:first-child { border-top: none; }
.te-fail-url {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 11px;
  color: #333;
  word-break: break-all;
}
.te-fail-msg {
  font-size: 11px;
  color: #888;
}

/* ── 降级 ── */
.raw-output {
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
