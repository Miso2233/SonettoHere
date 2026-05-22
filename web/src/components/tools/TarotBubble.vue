<template>
  <BubbleChrome :tool-call="toolCall">
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>塔罗占卜中...</span>
    </div>

    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '占卜失败' }}
    </div>

    <template v-else-if="toolCall.status === 'done'">
      <div v-if="cards.length" class="tarot-result">
        <div class="tarot-question">
          <span class="q-label">问：</span>{{ question }}
        </div>
        <div class="tarot-meta">
          <span class="meta-tag">{{ spreadName }}</span>
          <span class="meta-tag">{{ cards.length }} 张</span>
        </div>

        <!-- 横排布局：1~3 张 -->
        <div v-if="cards.length <= 3" class="cards-row">
          <div
            v-for="(card, i) in cards"
            :key="i"
            class="tarot-card"
            :class="{ reversed: card.status === '逆位' }"
          >
            <div class="card-position">{{ card.position }}</div>
            <div class="card-face" :style="{ borderColor: suitColor(card.suit) }">
              <div class="card-name">{{ card.name }}</div>
              <div class="card-name-en">{{ card.name_en }}</div>
              <div class="card-status" :class="card.status === '正位' ? 'upright' : 'reversed'">
                {{ card.status }}
              </div>
              <div class="card-tags">
                <span class="tag" :style="{ background: suitColor(card.suit) + '22', color: suitColor(card.suit) }">
                  {{ card.suit }}
                </span>
                <span class="tag">{{ card.element }}</span>
              </div>
              <div class="card-line"></div>
              <div class="card-keywords">
                <span v-for="(kw, ki) in card.keywords.slice(0, 3)" :key="ki" class="kw">{{ kw }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 竖排布局：4+ 张（凯尔特十字等） -->
        <div v-else class="cards-list">
          <div
            v-for="(card, i) in cards"
            :key="i"
            class="card-row"
            :class="{ reversed: card.status === '逆位' }"
          >
            <span class="card-row-num">{{ i + 1 }}</span>
            <div class="card-row-face" :style="{ borderLeftColor: suitColor(card.suit) }">
              <div class="card-row-top">
                <span class="card-row-name">{{ card.name }}</span>
                <span class="card-row-name-en">{{ card.name_en }}</span>
                <span class="card-row-status" :class="card.status === '正位' ? 'upright' : 'reversed'">
                  {{ card.status }}
                </span>
              </div>
              <div class="card-row-bottom">
                <span class="card-row-suit">{{ card.suit }}</span>
                <span class="card-row-pos">{{ card.position }}</span>
                <span class="card-row-kw">{{ card.keywords.slice(0, 2).join(' · ') }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

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

const SUIT_COLORS: Record<string, string> = {
  '大阿尔卡纳': '#b8860b',
  '权杖': '#d4522a',
  '圣杯': '#2a7ab5',
  '宝剑': '#6b7b8d',
  '星币': '#3d8b3d',
}

function suitColor(suit: string): string {
  return SUIT_COLORS[suit] || '#888'
}

// ── 数据源：优先 toolData，降级到 parse output ──
const data = computed(() => {
  if (props.toolCall.toolData) return props.toolCall.toolData
  if (props.toolCall.output) {
    try {
      const p = JSON.parse(props.toolCall.output)
      if (p?.data) return p.data
    } catch { /* ignore */ }
  }
  return null
})

const question = computed(() => (data.value?.question as string) || '')
const spreadName = computed(() => (data.value?.spread_name as string) || '')
const cards = computed<Array<Record<string, any>>>(() => {
  const raw = data.value?.cards as Array<Record<string, any>> | undefined
  return raw ?? []
})

// ── fallback 输出文本 ──
const displayOutput = computed(() => {
  if (props.toolCall.output) {
    const trimmed = props.toolCall.output.length > 500
      ? props.toolCall.output.slice(0, 500) + '...'
      : props.toolCall.output
    return trimmed
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

/* ── 问句与元信息 ── */
.tarot-question {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
  line-height: 1.5;
}

.q-label {
  color: var(--text-secondary);
  font-weight: 500;
}

.tarot-meta {
  display: flex;
  gap: 6px;
  margin-bottom: 14px;
}

.meta-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  font-weight: 500;
}

/* ── 横排卡片（1~3 张） ── */
.cards-row {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.tarot-card {
  flex: 1;
  min-width: 0;
  max-width: 200px;
}

.card-position {
  text-align: center;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.card-face {
  border: 2px solid #b8860b;
  border-radius: 10px;
  padding: 14px 10px;
  background: var(--bg-primary);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  transition: box-shadow 0.2s;
}

.tarot-card:hover .card-face {
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
}

.card-name {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
  text-align: center;
}

.card-name-en {
  font-size: 11px;
  color: var(--text-secondary);
  font-style: italic;
  text-align: center;
  line-height: 1.2;
  opacity: 0.75;
}

.card-status {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 10px;
  border-radius: 100px;
  margin: 2px 0;
}

.card-status.upright {
  background: #e8f5e8;
  color: #2d6a2d;
}

.card-status.reversed {
  background: #fde8e8;
  color: #a03030;
}

.card-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  justify-content: center;
}

.tag {
  font-size: 10px;
  padding: 1px 7px;
  border-radius: 3px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
}

.card-line {
  width: 30px;
  height: 1px;
  background: var(--border);
  margin: 2px 0;
}

.card-keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  justify-content: center;
}

.kw {
  font-size: 11px;
  color: var(--text-primary);
  padding: 1px 6px;
  background: var(--bg-secondary);
  border-radius: 3px;
  white-space: nowrap;
}

/* ── 竖排列表（4+ 张） ── */
.cards-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.card-row {
  display: flex;
  align-items: stretch;
  gap: 8px;
}

.card-row-num {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.card-row-face {
  flex: 1;
  padding: 8px 12px;
  background: var(--bg-primary);
  border-left: 3px solid #b8860b;
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.card-row-top {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-row-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.card-row-name-en {
  font-size: 11px;
  color: var(--text-secondary);
  font-style: italic;
}

.card-row-status {
  font-size: 10px;
  font-weight: 600;
  padding: 0 8px;
  border-radius: 100px;
  margin-left: auto;
}

.card-row-status.upright {
  background: #e8f5e8;
  color: #2d6a2d;
}

.card-row-status.reversed {
  background: #fde8e8;
  color: #a03030;
}

.card-row-bottom {
  display: flex;
  gap: 8px;
  font-size: 11px;
  color: var(--text-secondary);
}

.card-row-suit,
.card-row-pos {
  opacity: 0.8;
}

.card-row-kw {
  color: var(--text-primary);
  opacity: 0.6;
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
