<template>
  <BubbleChrome :tool-call="toolCall">
    <!-- 等待交互数据到达 -->
    <div v-if="toolCall.status === 'running' && !submitted && !interactionData.interactionId" class="ask-waiting">
      <span class="spinner"></span>
      <span>等待询问...</span>
    </div>

    <!-- 运行中：展示交互表单 -->
    <div v-else-if="toolCall.status === 'running' && !submitted && interactionData.interactionId" class="ask-body">
      <p class="ask-question">{{ interactionData.question }}</p>

      <!-- QA 模式：自由文本输入 -->
      <div v-if="interactionData.mode === 'qa'" class="qa-input-area">
        <textarea
          v-model="qaText"
          class="qa-textarea"
          placeholder="请输入你的回答..."
          rows="3"
        ></textarea>
        <button
          class="btn-submit"
          :disabled="!qaText.trim()"
          @click="submitQA"
        >
          发送
        </button>
      </div>

      <!-- 单项选择 -->
      <div v-else-if="interactionData.mode === 'single_choice'" class="choice-area">
        <label
          v-for="(opt, idx) in interactionData.options"
          :key="idx"
          class="choice-option"
          :class="{ selected: singleSelected === opt }"
        >
          <input
            type="radio"
            :value="opt"
            v-model="singleSelected"
            class="choice-radio"
          />
          <span class="choice-label">{{ opt }}</span>
        </label>
        <button
          class="btn-submit"
          :disabled="!singleSelected"
          @click="submitSingle"
        >
          确认选择
        </button>
      </div>

      <!-- 多项选择 -->
      <div v-else-if="interactionData.mode === 'multi_choice'" class="choice-area">
        <label
          v-for="(opt, idx) in interactionData.options"
          :key="idx"
          class="choice-option"
          :class="{ selected: multiSelected.includes(opt) }"
        >
          <input
            type="checkbox"
            :value="opt"
            v-model="multiSelected"
            class="choice-checkbox"
          />
          <span class="choice-label">{{ opt }}</span>
        </label>
        <button
          class="btn-submit"
          :disabled="multiSelected.length === 0"
          @click="submitMulti"
        >
          确认选择（{{ multiSelected.length }}）
        </button>
      </div>
    </div>

    <!-- 已提交，等待回复 -->
    <div v-else-if="toolCall.status === 'running' && submitted" class="ask-waiting">
      <span class="spinner"></span>
      <span>已提交，等待回复...</span>
    </div>

    <!-- 错误 -->
    <div v-else-if="toolCall.status === 'error'" class="ask-error">
      {{ toolCall.output || '交互失败' }}
    </div>

    <!-- 完成 -->
    <div v-else-if="toolCall.status === 'done'" class="ask-done">
      <div class="ask-done-icon">&#10003;</div>
      <p class="ask-done-label">已收到回复</p>
    </div>
  </BubbleChrome>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ToolCall } from '@/types'
import BubbleChrome from './_shared/BubbleChrome.vue'

const props = defineProps<{ toolCall: ToolCall }>()
const emit = defineEmits<{
  (e: 'action', p: { action: string; data?: unknown }): void
}>()

const submitted = ref(false)
const qaText = ref('')
const singleSelected = ref('')
const multiSelected = ref<string[]>([])

const interactionData = computed(() => {
  const result = props.toolCall.interaction
    ? props.toolCall.interaction
    : {
        question: '',
        mode: 'qa' as const,
        options: [] as string[],
        interactionId: '',
        submitted: false,
      }
  console.log('[AskUserBubble] interactionData computed:', {
    status: props.toolCall.status,
    submitted: submitted.value,
    hasInteraction: !!props.toolCall.interaction,
    interactionId: result.interactionId,
    mode: result.mode,
  })
  return result
})

function submitQA() {
  const text = qaText.value.trim()
  if (!text) return
  submitted.value = true
  emit('action', {
    action: 'user_response',
    data: {
      interactionId: interactionData.value.interactionId,
      response: text,
    },
  })
}

function submitSingle() {
  if (!singleSelected.value) return
  submitted.value = true
  emit('action', {
    action: 'user_response',
    data: {
      interactionId: interactionData.value.interactionId,
      response: singleSelected.value,
    },
  })
}

function submitMulti() {
  if (multiSelected.value.length === 0) return
  submitted.value = true
  emit('action', {
    action: 'user_response',
    data: {
      interactionId: interactionData.value.interactionId,
      response: multiSelected.value,
    },
  })
}
</script>

<style scoped>
.ask-body {
  padding: 4px 0;
}
.ask-question {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary);
  margin: 0 0 12px 0;
  font-weight: 500;
}

/* QA 输入 */
.qa-input-area {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.qa-textarea {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 13px;
  font-family: inherit;
  line-height: 1.5;
  resize: vertical;
  box-sizing: border-box;
  outline: none;
  transition: border-color 0.15s;
}
.qa-textarea:focus {
  border-color: var(--accent);
}
.qa-textarea::placeholder {
  color: var(--text-secondary);
}

/* 选项 */
.choice-area {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.choice-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.12s;
  background: var(--bg-primary);
}
.choice-option:hover {
  border-color: var(--accent);
}
.choice-option.selected {
  border-color: var(--accent);
  background: color-mix(in srgb, var(--accent) 8%, transparent);
}
.choice-radio,
.choice-checkbox {
  accent-color: var(--accent);
  flex-shrink: 0;
}
.choice-label {
  font-size: 13px;
  color: var(--text-primary);
}

/* 提交按钮 */
.btn-submit {
  align-self: flex-end;
  margin-top: 4px;
  padding: 6px 20px;
  border: none;
  border-radius: 6px;
  background: var(--accent);
  color: #fff;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  transition: background 0.15s;
}
.btn-submit:hover:not(:disabled) {
  background: #a07d4f;
}
.btn-submit:disabled {
  opacity: 0.4;
  cursor: default;
}

/* 等待中 */
.ask-waiting {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 0;
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

/* 错误 */
.ask-error {
  font-size: 13px;
  color: #c05050;
  padding: 4px 0;
}

/* 完成 */
.ask-done {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
}
.ask-done-icon {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #4caf50;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  flex-shrink: 0;
}
.ask-done-label {
  font-size: 13px;
  color: var(--text-primary);
  margin: 0;
}
</style>
