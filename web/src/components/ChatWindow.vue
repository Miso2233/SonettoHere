<template>
  <div class="chat-window" ref="windowRef">
    <div class="messages-list">
      <!-- 所有轮次（已完成 + 正在流式）合并在同一列表中，:key="turn.id" 确保
           组件实例在 turn 从当前轮过渡到已完成时不销毁重建，避免 iframe 闪烁 -->
      <template v-for="(turn, mergedIdx) in mergedTurns" :key="turn.id">
        <div
          class="cite-source"
          :data-user-msg-idx="turnsIndex(mergedIdx)"
          @contextmenu.prevent="onBubbleContextMenu($event, 'user_message', turn.userMessage, '用户', turnsIndex(mergedIdx))"
        >
          <MessageBubble role="user" :content="turn.userMessage" :refs="turn.refs" />
        </div>
        <template v-for="(ev, i) in turn.events" :key="i">
          <div
            v-if="ev.kind === 'thinking'"
            class="cite-source"
            @contextmenu.prevent="onBubbleContextMenu($event, 'thinking', ev.tokens, '思考过程')"
          >
            <ThinkingBlock :block="ev" />
          </div>
          <div
            v-else
            class="cite-source"
            @contextmenu.prevent="
              onBubbleContextMenu(
                $event,
                'tool_result',
                ev.output || ev.input || '',
                ev.name,
              )
            "
          >
            <ToolBubbleRouter :tool-call="ev" @action="forwardAction" />
          </div>
        </template>
        <!-- finalAnswer：仅在已完成（非流式）轮次中展示 -->
        <div
          v-if="turn.finalAnswer && !hasAnswerBlock(turn) && !isStreamingTurn(turn)"
          class="cite-source"
          @contextmenu.prevent="onBubbleContextMenu($event, 'assistant_message', turn.finalAnswer, 'AI')"
        >
          <MessageBubble role="assistant" :content="turn.finalAnswer" />
        </div>
      </template>

      <!-- 错误提示 -->
      <div v-if="error" class="error-banner">{{ error }}</div>

      <!-- 空状态 -->
      <div v-if="turns.length === 0 && !currentTurn" class="empty-state">
        <p class="empty-title">SonettoHere<svg viewBox="0 0 64 64" fill="currentColor" style="width:32px;height:32px;flex-shrink:0"><path d="M21.956,48.12,21.18,52H20a1,1,0,0,0-1,1v3a1,1,0,0,0,0,2v3a1,1,0,0,0,1,1H44a1,1,0,0,0,1-1V58a1,1,0,0,0,0-2V53a1,1,0,0,0-1-1H42.82l-.776-3.88A19.007,19.007,0,0,0,50.064,26.1a1,1,0,1,0-1.9.621,17.027,17.027,0,0,1-7.829,20.1.973.973,0,0,0-.208.18H33V43.916A6.95,6.95,0,0,0,39,37V32.708A1,1,0,0,0,37.293,32l-2.648,2.648a.378.378,0,0,1-.605-.1.382.382,0,0,1-.04-.169V28.708a1,1,0,0,0-1.581-.813L28.1,30.981A7.412,7.412,0,0,0,25,37a7.006,7.006,0,0,0,.4,2.339,1,1,0,0,0,1.885-.668A5,5,0,0,1,27,37a5.41,5.41,0,0,1,2.26-4.392L32,30.651v3.732a2.378,2.378,0,0,0,4.059,1.681L37,35.123V37a4.961,4.961,0,0,1-4,4.891V39a1,1,0,0,0-2,0v2.891a4.932,4.932,0,0,1-1.235-.418,4.992,4.992,0,0,1-.824-.518,1,1,0,0,0-1.224,1.582A6.851,6.851,0,0,0,31,43.916V47H23.873a.973.973,0,0,0-.208-.18A17,17,0,0,1,22.36,18H41.63a17.016,17.016,0,0,1,4.2,4.114,1,1,0,0,0,1.627-1.164A19,19,0,0,0,43,16.527V12a1,1,0,0,0-.445-.832l-3-2A1.006,1.006,0,0,0,39,9H37V7A5,5,0,0,0,27,7V9H25a1.006,1.006,0,0,0-.555.168l-3,2A1,1,0,0,0,21,12v4.517a18.984,18.984,0,0,0,.956,31.6ZM40.181,49l.6,3H31a1,1,0,0,0,0,2H43v2H31a1,1,0,0,0,0,2H43v2H21V58h2a1,1,0,0,0,0-2H21V54h5a1,1,0,0,0,0-2H23.22l.6-3ZM29,7a3,3,0,0,1,6,0V9H29Zm-6,5.535L25.3,11H38.7L41,12.535V16H23Z"/></svg></p>
        <p class="empty-desc">
          Built for <span class="typewriter">{{ displayedWord }}<span class="typewriter-cursor">|</span></span>
        </p>
        <div class="quick-hints">
          <span class="quick-hint">
            <span class="quick-hint-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="9" y1="3" x2="9" y2="21"/></svg></span>
            单击开关侧栏
          </span>
          <span class="quick-hint" @click="togglePrivate">
            <span class="quick-hint-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg></span>
            <span><kbd>Ctrl</kbd> + <kbd>K</kbd> 切换私密模式</span>
          </span>
          <span class="quick-hint"> <!-- will be wired to new-session -->
            <span class="quick-hint-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg></span>
            点击 <kbd>+</kbd> 新建会话
          </span>
        </div>
      </div>
    </div>

    <!-- 用户消息滚动标记 -->
    <div class="scroll-marks" v-if="turns.length > 0">
      <div
        v-for="(turn, idx) in turns"
        :key="turn.id"
        class="scroll-mark"
        @click="scrollToTurn(idx)"
        :title="turn.userMessage.slice(0, 60)"
      />
    </div>

    <ContextMenu
      :position="ctxMenuPos"
      :items="ctxMenuItems"
      :visible="ctxMenuVisible"
      @select="handleContextMenuSelect"
      @close="closeContextMenu"
    />
  </div>
</template>

<script setup lang="ts">
import type { ChatTurn } from '@/types'
import type { ParsedRef } from '@/utils/references'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import type { ContextMenuItem } from './ContextMenu.vue'
import ContextMenu from './ContextMenu.vue'
import MessageBubble from './MessageBubble.vue'
import ThinkingBlock from './ThinkingBlock.vue'
import ToolBubbleRouter from './ToolBubbleRouter.vue'

const props = defineProps<{
  turns: ChatTurn[]
  currentTurn: ChatTurn | null
  error: string | null
}>()

const emit = defineEmits<{
  (e: 'action', p: { action: string; data?: unknown }): void
  (e: 'cite', ref: ParsedRef): void
  (e: 'togglePrivate'): void
}>()

function forwardAction(payload: { action: string; data?: unknown }) {
  emit('action', payload)
}

const windowRef = ref<HTMLElement | null>(null)
const SCROLL_BOTTOM_THRESHOLD = 100

function isNearBottom(): boolean {
  const el = windowRef.value
  if (!el) return true
  return el.scrollHeight - el.scrollTop - el.clientHeight < SCROLL_BOTTOM_THRESHOLD
}

function hasAnswerBlock(turn: ChatTurn): boolean {
  return turn.events.some(e => e.kind === 'thinking' && e.becameAnswer)
}

/** 合并已完成轮次和当前流式轮次到单个列表，用 turn.id 作为 key，
 *  使组件实例在过渡时不被销毁重建 */
const mergedTurns = computed<ChatTurn[]>(() => {
  if (!props.currentTurn) return props.turns
  // currentTurn 可能已被 pushed 到 turns（becameAnswer 分支），去重
  if (props.turns.some(t => t.id === props.currentTurn!.id)) return props.turns
  return [...props.turns, props.currentTurn]
})

/** mergedTurns 中第 mergedIdx 项在 props.turns 中的索引（当前轮返回 -1） */
function turnsIndex(mergedIdx: number): number {
  // 前 props.turns.length 项索引与 mergedIdx 一致
  if (mergedIdx < props.turns.length) return mergedIdx
  return -1
}

/** 该轮次是否正在流式生成中 */
function isStreamingTurn(turn: ChatTurn): boolean {
  return props.currentTurn?.id === turn.id
}

function scrollToBottom() {
  nextTick(() => {
    const el = windowRef.value
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  })
}

function scrollToTurn(index: number) {
  const el = windowRef.value?.querySelector(`[data-user-msg-idx="${index}"]`)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

watch(() => props.turns.length, () => {
  if (isNearBottom()) scrollToBottom()
})
watch(
  () => props.currentTurn?.events.length,
  () => {
    if (isNearBottom()) scrollToBottom()
  }
)
watch(
  () => props.currentTurn?.finalAnswer,
  () => {
    if (isNearBottom()) scrollToBottom()
  }
)

// ── Typewriter: Built for Dream/Answer/Chatting/You ──
const words = ['Dreaming', 'Answers', 'Chatting', 'Creating', 'Connection', 'Building', 'Tinkering', 'Exploration', 'Heart', 'Logic', 'Empathy', 'You', 'Caring', 'Listening']
const displayedWord = ref(words[0])
let wordIndex = 0
let charIndex = words[0].length
let isDeleting = false
let typeTimer: ReturnType<typeof setTimeout> | null = null

function typewriterTick() {
  const current = words[wordIndex]
  if (!isDeleting) {
    if (charIndex < current.length) {
      charIndex++
      displayedWord.value = current.slice(0, charIndex) + (charIndex === current.length ? '.' : '')
      typeTimer = setTimeout(typewriterTick, 120)
    } else {
      // 打出完整词后暂停 1.5s 再开始删除
      isDeleting = true
      typeTimer = setTimeout(typewriterTick, 1500)
    }
  } else {
    if (charIndex > 0) {
      charIndex--
      displayedWord.value = current.slice(0, charIndex)
      typeTimer = setTimeout(typewriterTick, 80)
    } else {
      isDeleting = false
      wordIndex = (wordIndex + 1) % words.length
      charIndex = 0
      typeTimer = setTimeout(typewriterTick, 120)
    }
  }
}

// ── Private mode toggle (Ctrl+K) ──
function togglePrivate() {
  emit('togglePrivate')
}

function onPrivateKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault()
    togglePrivate()
  }
}

onMounted(() => {
  displayedWord.value = words[0]
  charIndex = words[0].length
  wordIndex = 0
  isDeleting = false
  typewriterTick()
  document.addEventListener('keydown', onPrivateKeydown)
})

onUnmounted(() => {
  if (typeTimer) clearTimeout(typeTimer)
  document.removeEventListener('keydown', onPrivateKeydown)
})

// === 引用功能 ===

const MAX_CITE_LENGTH = 1000

const ctxMenuVisible = ref(false)
const ctxMenuPos = ref({ x: 0, y: 0 })
const pendingCitation = ref<{ text: string } | null>(null)

/** 右键点击的用户消息在 turns 中的索引（-1 表示当前正在生成的 turn） */
const pendingUserMsgIdx = ref<number | null>(null)

const ctxMenuItems = computed((): ContextMenuItem[] => {
  const items: ContextMenuItem[] = [
    { label: '引用', action: 'cite', icon: 'cite-speech' },
    { label: '复制', action: 'copy', icon: 'copy' },
  ]
  // 仅在右键最后一条已完成用户消息时显示「撤回」
  if (
    pendingUserMsgIdx.value !== null
    && pendingUserMsgIdx.value === props.turns.length - 1
    && props.turns.length > 0
  ) {
    items.push({ label: '撤回', action: 'undo', icon: 'undo-arrow' })
  }
  return items
})

function onBubbleContextMenu(
  event: MouseEvent,
  _sourceType: string,
  fullText: string,
  _sourceLabel: string,
  userMsgIdx?: number,
) {
  pendingUserMsgIdx.value = userMsgIdx ?? null

  let citeText = fullText

  // 检查是否有文本选中
  const selection = window.getSelection()
  const selectedText = selection?.toString().trim()
  if (selectedText && selection!.rangeCount > 0) {
    const range = selection!.getRangeAt(0)
    const target = event.currentTarget as HTMLElement | null
    if (target && target.contains(range.commonAncestorContainer)) {
      citeText = selectedText
    }
    selection!.removeAllRanges()
  }

  if (!citeText) return

  if (citeText.length > MAX_CITE_LENGTH) {
    citeText = citeText.slice(0, MAX_CITE_LENGTH) + '…'
  }

  pendingCitation.value = { text: citeText }
  ctxMenuPos.value = { x: event.clientX, y: event.clientY }
  ctxMenuVisible.value = true
}

function handleContextMenuSelect(action: string) {
  if (action === 'cite' && pendingCitation.value) {
    const label = pendingCitation.value.text.length > 80
      ? pendingCitation.value.text.slice(0, 80) + '…'
      : pendingCitation.value.text
    const citeRef: ParsedRef = { type: 'cite', text: pendingCitation.value.text, label }
    emit('cite', citeRef)
  } else if (action === 'copy' && pendingCitation.value) {
    navigator.clipboard.writeText(pendingCitation.value.text)
  } else if (action === 'undo') {
    emit('action', { action: 'undo', data: { n: 1 } })
  }
  closeContextMenu()
}

function closeContextMenu() {
  ctxMenuVisible.value = false
  pendingCitation.value = null
  pendingUserMsgIdx.value = null
}
</script>

<style scoped>
.chat-window {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  background: #ffffff;
}
.messages-list {
  max-width: 768px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.messages-list:has(.empty-state) {
  height: 100%;
}
.cite-source {
  /* 包装层，不引入额外布局影响 */
}
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  height: 100%;
  padding: 0 0 0 48px;
  gap: 8px;
}
.empty-state::before {
  content: '';
  display: block;
  width: 40px;
  height: 2px;
  background: var(--border);
  margin-bottom: 4px;
}
.empty-title {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 42px;
  font-weight: 700;
  letter-spacing: -0.5px;
  background: linear-gradient(135deg, #000000 40%, #555555 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.empty-desc {
  font-size: 20px;
  color: var(--text-secondary);
}
.typewriter {
  display: inline-block;
  min-width: 1ch;
}
.typewriter-cursor {
  display: inline-block;
  margin-left: 1px;
  font-weight: 300;
  color: var(--text-secondary);
  animation: blink 0.7s step-end infinite;
}
@keyframes blink {
  50% { opacity: 0; }
}

/* ── Quick hints (from variant D) ── */
.quick-hints {
  margin-top: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  opacity: .55;
  transition: opacity .2s;
}
.quick-hints:hover {
  opacity: .85;
}
.quick-hint {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  cursor: default;
  transition: color .15s;
}
.quick-hint kbd {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 22px;
  padding: 0 5px;
  font-size: 11px;
  font-family: inherit;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text-secondary);
  box-shadow: 0 1px 0 var(--border);
}
.quick-hint-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  color: var(--text-secondary);
  flex-shrink: 0;
}
.quick-hint:hover {
  color: var(--accent);
  cursor: pointer;
}
.error-banner {
  padding: 10px 16px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: var(--radius);
  color: #b91c1c;
  font-size: 13px;
}

/* ── 右侧滚动标记 ── */
.scroll-marks {
  --item-gap: 18px;

  position: fixed;
  right: max(12px, calc((100vw - 1036px) / 4 + 12px));
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--item-gap);
  z-index: 100;
  pointer-events: none;
}

.scroll-mark {
  position: relative;
  width: 18px;
  height: 4px;
  border-radius: 2px;
  background: var(--border);
  cursor: pointer;
  pointer-events: auto;
  transition: background 0.15s, width 0.15s;
  flex-shrink: 0;
}

/* 不可见的悬停/点击判定区，以横条为中心上下各延展 gap/2 */
.scroll-mark::before {
  content: '';
  position: absolute;
  left: -12px;
  right: -12px;
  top: calc(var(--item-gap) / -2);
  bottom: calc(var(--item-gap) / -2);
}

.scroll-mark:hover {
  background: var(--accent);
  width: 24px;
}

.scroll-mark:active {
  background: var(--accent-light);
}
</style>
