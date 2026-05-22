<template>
  <BubbleChrome :tool-call="toolCall">
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>抓取网页...</span>
    </div>

    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '抓取失败' }}
    </div>

    <template v-else-if="toolCall.status === 'done'">
      <div v-if="hasData" class="sc-result">
        <!-- ═══ 页面信息卡片 ═══ -->
        <div class="sc-page-card">
          <div class="sc-page-icon">🌐</div>
          <div class="sc-page-info">
            <div v-if="td.title" class="sc-page-title">{{ td.title }}</div>
            <div class="sc-page-url">{{ td.url }}</div>
          </div>
        </div>

        <!-- ═══ 开放图谱 ═══ -->
        <div v-if="ogKeys.length" class="sc-section">
          <div class="bubble-section-title">开放图谱</div>
          <div class="sc-og-card">
            <div class="sc-og-body">
              <div v-for="k in ogKeys" :key="k" class="sc-og-row">
                <span class="sc-og-key">{{ k }}</span>
                <span class="sc-og-val">{{ og[k] }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- ═══ 标题结构 ═══ -->
        <div v-if="headingsList.length" class="sc-section">
          <div class="bubble-section-title">
            页面标题结构（{{ headingsList.length }}）
            <span class="sc-toggle" @click="showHeadings = !showHeadings">{{ showHeadings ? '▾' : '▸' }}</span>
          </div>
          <div v-if="showHeadings" class="sc-headings">
            <div v-for="(h, i) in headingsList" :key="i" class="sc-heading-item" :style="{ paddingLeft: (h.level - 1) * 16 + 8 + 'px' }">
              <span class="sc-heading-badge">H{{ h.level }}</span>
              <span class="sc-heading-text">{{ h.text }}</span>
            </div>
          </div>
        </div>

        <!-- ═══ 链接 ═══ -->
        <div v-if="linksList.length" class="sc-section">
          <div class="bubble-section-title">
            链接（{{ linksList.length }}）
            <span class="sc-toggle" @click="showLinks = !showLinks">{{ showLinks ? '▾' : '▸' }}</span>
          </div>
          <div v-if="showLinks" class="sc-links">
            <div v-for="(link, i) in displayedLinks" :key="i" class="sc-link-item">
              <span v-if="link.text" class="sc-link-text">{{ link.text }}</span>
              <span class="sc-link-href">{{ link.href }}</span>
            </div>
            <div v-if="linksList.length > 50" class="sc-link-more">还有 {{ linksList.length - 50 }} 个链接...</div>
          </div>
        </div>

        <!-- ═══ 图片 ═══ -->
        <div v-if="imagesList.length" class="sc-section">
          <div class="bubble-section-title">
            图片（{{ imagesList.length }}）
            <span class="sc-toggle" @click="showImages = !showImages">{{ showImages ? '▾' : '▸' }}</span>
          </div>
          <div v-if="showImages" class="sc-images">
            <div v-for="(img, i) in imagesList.slice(0, 20)" :key="i" class="sc-img-item">
              <img :src="img.src" :alt="img.alt || ''" class="sc-img-thumb" @error="($event.target as HTMLImageElement).style.display = 'none'" />
              <span v-if="img.alt" class="sc-img-alt">{{ img.alt }}</span>
            </div>
            <div v-if="imagesList.length > 20" class="sc-link-more">还有 {{ imagesList.length - 20 }} 张图片...</div>
          </div>
        </div>

        <!-- ═══ 结构化数据 ═══ -->
        <div v-if="sdList.length" class="sc-section">
          <div class="bubble-section-title">
            结构化数据（{{ sdList.length }}）
            <span class="sc-toggle" @click="showSD = !showSD">{{ showSD ? '▾' : '▸' }}</span>
          </div>
          <div v-if="showSD">
            <pre v-for="(sd, i) in sdList" :key="i" class="sc-sd-block">{{ JSON.stringify(sd, null, 2) }}</pre>
          </div>
        </div>

        <!-- ═══ 截图 ═══ -->
        <div v-if="td.screenshot_base64" class="sc-section">
          <div class="bubble-section-title">页面截图</div>
          <img :src="'data:image/png;base64,' + td.screenshot_base64" class="sc-screenshot" alt="screenshot" />
        </div>
      </div>

      <div v-else class="raw-output">{{ displayOutput }}</div>
    </template>
  </BubbleChrome>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ToolCall } from '@/types'
import BubbleChrome from './_shared/BubbleChrome.vue'

const props = defineProps<{ toolCall: ToolCall }>()
defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

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

// ── Open Graph ──
const og = computed(() => (td.value.open_graph || {}) as Record<string, string>)
const ogKeys = computed(() => Object.keys(og.value))

// ── Headings ──
const showHeadings = ref(false)
const headingsList = computed<Array<Record<string, any>>>(() => {
  const h = td.value.headings
  return Array.isArray(h) ? h : []
})

// ── Links ──
const showLinks = ref(false)
const linksList = computed<Array<Record<string, any>>>(() => {
  const l = td.value.links
  return Array.isArray(l) ? l : []
})
const displayedLinks = computed(() => linksList.value.slice(0, 50))

// ── Images ──
const showImages = ref(false)
const imagesList = computed<Array<Record<string, any>>>(() => {
  const im = td.value.images
  return Array.isArray(im) ? im : []
})

// ── Structured Data ──
const showSD = ref(false)
const sdList = computed<Array<Record<string, any>>>(() => {
  const s = td.value.structured_data
  return Array.isArray(s) ? s : []
})

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
.bubble-running { display: flex; align-items: center; gap: 8px; padding: 8px 0; font-size: 13px; color: var(--text-secondary); }

.bubble-error { font-size: 13px; color: #b91c1c; padding: 4px 0; }

.sc-result { display: flex; flex-direction: column; gap: 12px; padding: 4px 0; }
.sc-section { display: flex; flex-direction: column; gap: 8px; }

/* ── Page Card ── */
.sc-page-card { display: flex; align-items: center; gap: 12px; padding: 12px 14px; background: var(--bg-secondary); border-radius: 8px; }
.sc-page-icon { font-size: 28px; flex-shrink: 0; }
.sc-page-info { flex: 1; min-width: 0; }
.sc-page-title { font-size: 14px; font-weight: 600; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sc-page-url { font-size: 11px; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* ── OG Card ── */
.sc-og-card { display: flex; flex-direction: column; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; background: var(--bg-primary); }
.sc-og-body { display: flex; flex-direction: column; gap: 6px; padding: 10px 12px; }
.sc-og-row { display: flex; gap: 8px; font-size: 12px; }
.sc-og-key { font-weight: 600; color: var(--accent); flex-shrink: 0; min-width: 80px; }
.sc-og-val { color: var(--text-primary); word-break: break-all; }

/* ── Headings ── */
.sc-toggle { cursor: pointer; font-size: 12px; color: var(--text-secondary); }
.sc-headings { display: flex; flex-direction: column; gap: 2px; }
.sc-heading-item { display: flex; align-items: center; gap: 8px; padding: 5px 8px; font-size: 13px; }
.sc-heading-item:hover { background: var(--bg-secondary); border-radius: 4px; }
.sc-heading-badge { font-size: 10px; font-weight: 700; color: var(--accent); background: var(--bg-secondary); padding: 1px 6px; border-radius: 3px; flex-shrink: 0; }
.sc-heading-text { color: var(--text-primary); }

/* ── Links ── */
.sc-links { display: flex; flex-direction: column; gap: 3px; max-height: 300px; overflow-y: auto; }
.sc-link-item { display: flex; flex-direction: column; gap: 2px; padding: 6px 10px; background: var(--bg-primary); border: 1px solid var(--border); border-radius: 4px; }
.sc-link-text { font-size: 12px; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sc-link-href { font-size: 11px; color: var(--accent); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sc-link-more { font-size: 11px; color: var(--text-secondary); text-align: center; padding: 4px; }

/* ── Images ── */
.sc-images { display: flex; flex-wrap: wrap; gap: 8px; }
.sc-img-item { display: flex; flex-direction: column; gap: 4px; width: 120px; }
.sc-img-thumb { width: 120px; height: 80px; object-fit: cover; border-radius: 4px; border: 1px solid var(--border); }
.sc-img-alt { font-size: 10px; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* ── Structured Data ── */
.sc-sd-block { font-size: 11px; line-height: 1.5; color: var(--text-primary); padding: 8px 10px; background: var(--bg-primary); border: 1px solid var(--border); border-radius: 4px; max-height: 200px; overflow-y: auto; margin: 4px 0; font-family: 'SF Mono', 'Consolas', monospace; white-space: pre; }

/* ── Screenshot ── */
.sc-screenshot { width: 100%; border-radius: 6px; border: 1px solid var(--border); }

.raw-output { font-family: 'SF Mono', 'Consolas', monospace; font-size: 12px; color: var(--text-primary); white-space: pre-wrap; word-break: break-word; margin: 0; padding: 8px 12px; background: var(--bg-primary); border-radius: 6px; }
</style>
