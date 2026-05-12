<template>
  <div class="chat-input-wrapper">
    <div class="chat-input">
      <textarea
        ref="textareaRef"
        v-model="text"
        class="input-area"
        placeholder="输入消息……"
        :disabled="disabled"
        rows="1"
        @keydown.enter.exact.prevent="handleSend"
        @input="autoResize"
      ></textarea>
      <div class="input-actions">
        <button
          v-if="!isStreaming"
          class="btn-send"
          :disabled="!text.trim() || disabled"
          @click="handleSend"
        >
          发送
        </button>
        <button v-else class="btn-stop" @click="$emit('stop')">
          停止
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'

const props = defineProps<{
  isStreaming: boolean
  disabled: boolean
}>()

const emit = defineEmits<{
  send: [message: string]
  stop: []
}>()

const text = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)

function handleSend() {
  const msg = text.value.trim()
  if (!msg || props.disabled) return
  emit('send', msg)
  text.value = ''
  nextTick(() => autoResize())
}

function autoResize() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 160) + 'px'
}
</script>

<style scoped>
.chat-input-wrapper {
  border-top: 1px solid var(--border);
  padding: 16px 24px;
  background: var(--bg-card);
}
.chat-input {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 10px 14px;
  transition: border-color 0.15s;
}
.chat-input:focus-within {
  border-color: var(--accent);
}
.input-area {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14px;
  line-height: 1.5;
  color: var(--text-primary);
  resize: none;
  font-family: inherit;
}
.input-area::placeholder {
  color: var(--text-secondary);
}
.input-actions {
  display: flex;
  gap: 6px;
  align-items: center;
}
.btn-send,
.btn-stop {
  padding: 6px 16px;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
  font-family: inherit;
}
.btn-send {
  background: var(--accent);
  color: #fff;
}
.btn-send:hover:not(:disabled) {
  background: #a07d4f;
}
.btn-send:disabled {
  opacity: 0.4;
  cursor: default;
}
.btn-stop {
  background: #c97a7a;
  color: #fff;
}
.btn-stop:hover {
  background: #b55a5a;
}
</style>
