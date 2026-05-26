<template>
  <div class="chat-window" ref="windowRef">
    <div class="messages-list">
      <!-- 已完成的消息轮次 -->
      <template v-for="(turn, idx) in turns" :key="turn.id">
        <div
          class="cite-source"
          :data-user-msg-idx="idx"
          @contextmenu.prevent="onBubbleContextMenu($event, 'user_message', turn.userMessage, '用户')"
        >
          <MessageBubble role="user" :content="turn.userMessage" />
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
        <div
          v-if="turn.finalAnswer && !hasAnswerBlock(turn)"
          class="cite-source"
          @contextmenu.prevent="onBubbleContextMenu($event, 'assistant_message', turn.finalAnswer, 'AI')"
        >
          <MessageBubble role="assistant" :content="turn.finalAnswer" />
        </div>
      </template>

      <!-- 当前正在流式生成的消息 -->
      <template v-if="currentTurn">
        <div
          class="cite-source"
          @contextmenu.prevent="onBubbleContextMenu($event, 'user_message', currentTurn.userMessage, '用户')"
        >
          <MessageBubble role="user" :content="currentTurn.userMessage" />
        </div>
        <template v-for="(ev, i) in currentTurn.events" :key="i">
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
      </template>

      <!-- 错误提示 -->
      <div v-if="error" class="error-banner">{{ error }}</div>

      <!-- 空状态 -->
      <div v-if="turns.length === 0 && !currentTurn" class="empty-state">
        <p class="empty-title">SonettoHere</p>
        <p class="empty-desc">发送一条消息开始对话</p>
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
import { watch, ref, nextTick } from 'vue'
import type { ChatTurn, Citation } from '@/types'
import MessageBubble from './MessageBubble.vue'
import ThinkingBlock from './ThinkingBlock.vue'
import ToolBubbleRouter from './ToolBubbleRouter.vue'
import ContextMenu from './ContextMenu.vue'
import type { ContextMenuItem } from './ContextMenu.vue'

const props = defineProps<{
  turns: ChatTurn[]
  currentTurn: ChatTurn | null
  error: string | null
}>()

const emit = defineEmits<{
  (e: 'action', p: { action: string; data?: unknown }): void
  (e: 'cite', citation: Citation): void
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

// === 引用功能 ===

const MAX_CITE_LENGTH = 1000

const ctxMenuVisible = ref(false)
const ctxMenuPos = ref({ x: 0, y: 0 })
const pendingCitation = ref<{
  text: string
  sourceLabel: string
  sourceType: Citation['sourceType']
} | null>(null)

const ctxMenuItems: ContextMenuItem[] = [
  { label: '引用', action: 'cite', icon: 'cite-speech' },
  { label: '复制', action: 'copy', icon: 'copy' },
]

function onBubbleContextMenu(
  event: MouseEvent,
  sourceType: Citation['sourceType'],
  fullText: string,
  sourceLabel: string,
) {
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

  pendingCitation.value = { text: citeText, sourceLabel, sourceType }
  ctxMenuPos.value = { x: event.clientX, y: event.clientY }
  ctxMenuVisible.value = true
}

function handleContextMenuSelect(action: string) {
  if (action === 'cite' && pendingCitation.value) {
    const citation: Citation = {
      id: crypto.randomUUID(),
      text: pendingCitation.value.text,
      sourceLabel: pendingCitation.value.sourceLabel,
      sourceType: pendingCitation.value.sourceType,
    }
    emit('cite', citation)
  } else if (action === 'copy' && pendingCitation.value) {
    navigator.clipboard.writeText(pendingCitation.value.text)
  }
  closeContextMenu()
}

function closeContextMenu() {
  ctxMenuVisible.value = false
  pendingCitation.value = null
}
</script>

<style scoped>
.chat-window {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}
.messages-list {
  max-width: 768px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.cite-source {
  /* 包装层，不引入额外布局影响 */
}
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 120px 20px 80px;
  gap: 12px;
}
.empty-title {
  font-size: 26px;
  font-weight: 600;
  color: var(--text-primary);
}
.empty-desc {
  font-size: 15px;
  color: var(--text-secondary);
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
