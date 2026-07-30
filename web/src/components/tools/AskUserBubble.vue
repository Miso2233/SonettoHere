<template>
  <BubbleChrome :tool-call="toolCall">
    <!-- 等待交互数据到达 -->
    <div v-if="toolCall.status === 'running' && !submitted && !interactionData.interactionId" class="ask-waiting">
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

        <!-- 单项选择：告诉Sonetto别的意见 -->
        <div class="other-choice-area">
          <button
            v-if="!showSingleOther"
            class="btn-other-toggle"
            @click="showSingleOther = true"
          >
            告诉Sonetto别的意见 ✎
          </button>
          <div v-else class="other-input-group">
            <textarea
              v-model="singleOtherText"
              class="other-textarea"
              placeholder="在此输入你的想法..."
              rows="2"
            ></textarea>
          </div>
        </div>

        <button
          class="btn-submit"
          :disabled="!singleSelected && !singleOtherText.trim()"
          @click="submitSingle"
        >
          确认选择{{ singleOtherText.trim() ? '（含自定义意见）' : '' }}
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

        <!-- 多项选择：告诉Sonetto别的意见 -->
        <div class="other-choice-area">
          <button
            v-if="!showMultiOther"
            class="btn-other-toggle"
            @click="showMultiOther = true"
          >
            告诉Sonetto别的意见 ✎
          </button>
          <div v-else class="other-input-group">
            <textarea
              v-model="multiOtherText"
              class="other-textarea"
              placeholder="在此输入你的想法..."
              rows="2"
            ></textarea>
          </div>
        </div>

        <button
          class="btn-submit"
          :disabled="multiSelected.length === 0 && !multiOtherText.trim()"
          @click="submitMulti"
        >
          确认选择（{{ multiOtherText.trim() ? multiSelected.length + 1 : multiSelected.length }}）
        </button>
      </div>
    </div>

    <!-- 已提交，等待回复 -->
    <div v-else-if="toolCall.status === 'running' && submitted" class="ask-waiting">
      <span>已提交，等待回复...</span>
    </div>

    <!-- 错误 -->
    <div v-else-if="toolCall.status === 'error'" class="ask-error">
      {{ toolCall.output || '交互失败' }}
    </div>

    <!-- 完成 -->
    <div v-else-if="toolCall.status === 'done'" class="ask-done">
      <div class="ask-done-summary">
        <div class="ask-done-icon">&#10003;</div>
        <span class="ask-done-label">已收到你的回复</span>
      </div>
      <div v-if="doneData" class="ask-done-detail">
        <div class="ask-done-item">
          <span class="ask-done-field">Q：</span>
          <span class="ask-done-value">{{ doneData.question }}</span>
        </div>
        <div class="ask-done-item">
          <span class="ask-done-field">A：</span>
          <span class="ask-done-value">{{ doneAnswer }}</span>
        </div>
      </div>
    </div>
  </BubbleChrome>
</template>

<script setup lang="ts">
import type { ToolCall } from '@/types';
import { computed, ref } from 'vue';
import BubbleChrome from './_shared/BubbleChrome.vue';

const props = defineProps<{ toolCall: ToolCall }>()
const emit = defineEmits<{
  (e: 'action', p: { action: string; data?: unknown }): void
}>()

/** 自定义文本前缀，用于在 response 中区分选中的选项和用户手写输入 */
const CUSTOM_TEXT_PREFIX = '__custom__::'

const submitted = ref(false)
const qaText = ref('')
const singleSelected = ref('')
const multiSelected = ref<string[]>([])

/** 单项选择「告诉Sonetto别的意见」状态 */
const showSingleOther = ref(false)
const singleOtherText = ref('')

/** 多项选择「告诉Sonetto别的意见」状态 */
const showMultiOther = ref(false)
const multiOtherText = ref('')

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
  return result
})

/** 工具完成时从 output JSON 解析出 { question, answer } */
const doneData = computed(() => {
  if (props.toolCall.status !== 'done' || !props.toolCall.output) return null
  try {
    const parsed = JSON.parse(props.toolCall.output)
    if (parsed.success && parsed.data) {
      return parsed.data as { question: string; answer: string | string[] }
    }
  } catch {}
  return null
})

/** 格式化用户的回答（多选时用顿号连接，自定义文本移除前缀标记） */
const doneAnswer = computed(() => {
  if (!doneData.value) return ''
  const answer = doneData.value.answer
  if (Array.isArray(answer)) {
    return answer
      .map(a => a.startsWith(CUSTOM_TEXT_PREFIX) ? a.slice(CUSTOM_TEXT_PREFIX.length) : a)
      .join('、')
  }
  if (typeof answer === 'string' && answer.startsWith(CUSTOM_TEXT_PREFIX)) {
    return answer.slice(CUSTOM_TEXT_PREFIX.length)
  }
  return answer || ''
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
  const response: string[] = []
  if (singleSelected.value) {
    response.push(singleSelected.value)
  }
  const other = singleOtherText.value.trim()
  if (other) {
    response.push(CUSTOM_TEXT_PREFIX + other)
  }
  if (response.length === 0) return
  submitted.value = true
  emit('action', {
    action: 'user_response',
    data: {
      interactionId: interactionData.value.interactionId,
      // 单选且无自定义文本时保持字符串，向后兼容
      response: response.length === 1 && !other ? response[0] : response,
    },
  })
}

function submitMulti() {
  const response: string[] = []
  // 已选中的选项
  response.push(...multiSelected.value)
  // 自定义文本
  const other = multiOtherText.value.trim()
  if (other) {
    response.push(CUSTOM_TEXT_PREFIX + other)
  }
  if (response.length === 0) return
  submitted.value = true
  emit('action', {
    action: 'user_response',
    data: {
      interactionId: interactionData.value.interactionId,
      response,
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

/* ── 告诉Sonetto别的意见 ── */
.other-choice-area {
  margin-top: 2px;
}
.btn-other-toggle {
  width: 100%;
  padding: 8px 12px;
  border: 1px dashed var(--border);
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
  text-align: left;
}
.btn-other-toggle:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 4%, transparent);
}
.other-input-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.other-textarea {
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
.other-textarea:focus {
  border-color: var(--accent);
}
.other-textarea::placeholder {
  color: var(--text-secondary);
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
  background: #1d4ed8;
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
/* 错误 */
.ask-error {
  font-size: 13px;
  color: #b91c1c;
  padding: 4px 0;
}

/* 完成 */
.ask-done {
  padding: 4px 0;
}
.ask-done-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
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
  font-weight: 500;
}
.ask-done-detail {
  margin-left: 28px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ask-done-item {
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-primary);
}
.ask-done-field {
  color: var(--text-secondary);
}
</style>
