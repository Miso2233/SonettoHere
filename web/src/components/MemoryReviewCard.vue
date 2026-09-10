<template>
  <div class="review-card" :class="stateClass">
    <!-- 头部：脑形图标与上方 callback 小图标呼应，右侧是主题胶囊 + 中文标签 -->
    <div class="rc-head">
      <span class="rc-glyph">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44A2.5 2.5 0 0 1 4 17.5V8a2.5 2.5 0 0 1 2.54-2.5A2.5 2.5 0 0 1 9.5 2Z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44A2.5 2.5 0 0 0 20 17.5V8a2.5 2.5 0 0 0-2.54-2.5A2.5 2.5 0 0 0 14.5 2Z"/></svg>
      </span>
      <span class="rc-title">记忆复核</span>
      <span class="rc-kind">· {{ kindLabel }}</span>
      <span class="rc-spacer"></span>
      <span class="rc-theme">{{ review.theme }}</span>
      <span class="rc-theme-label">{{ review.themeLabel }}</span>
    </div>

    <p class="rc-desc">{{ review.description }}</p>

    <div class="rc-foot">
      <span class="rc-id">ID {{ review.memoryId }}</span>

      <!-- 待处理：批准 / 拒绝 -->
      <div v-if="isPending" class="rc-actions">
        <button
          class="rc-btn rc-btn-reject"
          :disabled="review.submitting"
          @click="decide('reject')"
        >拒绝</button>
        <button
          class="rc-btn rc-btn-approve"
          :disabled="review.submitting"
          @click="decide('approve')"
        >批准</button>
      </div>

      <!-- 已决：终态标记 -->
      <div v-else class="rc-verdict">
        <span v-if="review.status === 'approved'" class="rc-verdict-mark">&#10003;</span>
        {{ verdictText }}
      </div>
    </div>

    <div v-if="!isPending && review.detail" class="rc-verdict-detail">{{ review.detail }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { MemoryReview } from '@/types'

const props = defineProps<{ review: MemoryReview }>()
const emit = defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

const isPending = computed(() => props.review.status === 'pending')

/** 已决状态的视觉变体：已撤销给正文加删除线，已失效用虚线边框，撤销失败单独标色。 */
const stateClass = computed(() => ({
  'is-resolved': !isPending.value,
  'is-rejected': props.review.status === 'rejected',
  'is-expired': props.review.status === 'expired',
  'is-error': props.review.status === 'error',
}))

const kindLabel = computed(() => (props.review.kind === 'create' ? '新建' : props.review.kind))

const VERDICT_TEXT: Record<string, string> = {
  approved: '已保留',
  rejected: '已撤销',
  expired: '已失效',
  error: '撤销失败',
  pending: '',
}

const verdictText = computed(() => VERDICT_TEXT[props.review.status] ?? props.review.status)

function decide(decision: 'approve' | 'reject') {
  emit('action', {
    action: 'memory_review_decision',
    data: { reviewId: props.review.reviewId, decision },
  })
}
</script>

<style scoped>
.review-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  padding: 12px 14px 11px;
  margin-top: 4px;
  margin-bottom: 8px;
  max-width: 560px;
  display: flex;
  flex-direction: column;
  gap: 9px;
  animation: rc-in 0.28s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes rc-in {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* ── 头部 ── */
.rc-head {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
}

.rc-glyph {
  display: inline-flex;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.rc-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  flex-shrink: 0;
}

.rc-kind {
  font-size: 11px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.rc-spacer {
  flex: 1 1 auto;
}

.rc-theme {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.6px;
  color: var(--text-primary);
  border: 1px solid var(--text-primary);
  border-radius: 4px;
  padding: 1px 5px;
  line-height: 1.5;
  flex-shrink: 0;
}

.rc-theme-label {
  font-size: 11px;
  color: var(--text-tertiary);
  white-space: nowrap;
  flex-shrink: 0;
}

/* ── 正文 ── */
.rc-desc {
  font-size: 13.5px;
  line-height: 1.65;
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

/* ── 底部 ── */
.rc-foot {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 1px;
}

.rc-id {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 10.5px;
  color: var(--text-tertiary);
  letter-spacing: 0.2px;
  flex-shrink: 0;
}

.rc-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.rc-btn {
  font-family: inherit;
  font-size: 12px;
  font-weight: 500;
  line-height: 1;
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s, opacity 0.15s;
}

.rc-btn-reject {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border);
}

.rc-btn-reject:hover:not(:disabled) {
  color: var(--text-primary);
  border-color: var(--accent-light);
}

.rc-btn-approve {
  background: var(--accent);
  color: #ffffff;
  border: 1px solid var(--accent);
}

.rc-btn-approve:hover:not(:disabled) {
  background: #1f1f1f;
  border-color: #1f1f1f;
}

.rc-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

/* ── 已决状态 ── */
.review-card.is-resolved {
  background: var(--bg-secondary);
  box-shadow: none;
}

.review-card.is-resolved .rc-desc {
  color: var(--text-secondary);
}

.review-card.is-resolved .rc-theme {
  color: var(--text-tertiary);
  border-color: var(--border);
}

/* 已撤销：正文划掉，让用户看清删掉的是哪条 */
.review-card.is-rejected .rc-desc {
  text-decoration: line-through;
  text-decoration-color: var(--text-tertiary);
  color: var(--text-tertiary);
}

/* 已失效：服务重启后点旧卡片 */
.review-card.is-expired {
  border-style: dashed;
  opacity: 0.75;
}

/* 撤销失败：条目仍在，需用户手动处理 */
.review-card.is-error {
  border-color: #fca5a5;
}

.rc-verdict {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.rc-verdict-mark {
  font-size: 11px;
  line-height: 1;
}

.review-card.is-error .rc-verdict {
  color: #b91c1c;
}

.rc-verdict-detail {
  font-size: 11px;
  color: var(--text-tertiary);
  line-height: 1.6;
  padding-top: 1px;
  overflow-wrap: anywhere;
}

.review-card.is-error .rc-verdict-detail {
  color: #b91c1c;
}
</style>
