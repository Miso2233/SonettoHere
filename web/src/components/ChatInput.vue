<template>
  <div class="chat-input-wrapper">
    <div v-if="filePaths.length" class="file-refs-bar">
      <span
        v-for="(fp, idx) in filePaths"
        :key="idx"
        class="file-tag"
        :title="fp"
      >
        <span class="file-tag-icon">📎</span>
        <span class="file-tag-name">{{ getFileName(fp) }}</span>
        <button class="file-tag-remove" @click="removeFile(idx)">✕</button>
      </span>
    </div>
    <div class="chat-input">
      <div class="btn-add-file-wrapper">
        <button class="btn-add-file" :disabled="disabled" @click="toggleMenu">
          <span v-if="loading" class="btn-add-file-spin">⟳</span>
          <span v-else>＋</span>
        </button>
        <div v-if="showMenu" class="add-file-menu" @click.stop>
          <button class="add-file-menu-item" @click="pickFile">
            <span class="menu-item-icon">📄</span> 选择文件
          </button>
          <button class="add-file-menu-item" @click="pickFolder">
            <span class="menu-item-icon">📁</span> 选择文件夹
          </button>
        </div>
        <div v-if="showMenu" class="menu-backdrop" @click="showMenu = false"></div>
      </div>
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
const filePaths = ref<string[]>([])
const loading = ref(false)
const showMenu = ref(false)

function getFileName(fp: string): string {
  const parts = fp.replace(/\\/g, '/').split('/')
  return parts[parts.length - 1] || fp
}

function toggleMenu() {
  if (props.disabled) return
  showMenu.value = !showMenu.value
}

async function pickFile() {
  showMenu.value = false
  await _pick('file')
}

async function pickFolder() {
  showMenu.value = false
  await _pick('folder')
}

async function _pick(type: string) {
  if (loading.value) return
  loading.value = true
  try {
    const res = await fetch(`/api/select-file?type=${type}`)
    const data = await res.json()
    if (data.path) {
      filePaths.value.push(data.path)
    }
  } catch {
    // 静默失败
  } finally {
    loading.value = false
  }
}

function removeFile(index: number) {
  filePaths.value.splice(index, 1)
}

function handleSend() {
  const msg = text.value.trim()
  if (!msg || props.disabled) return

  let finalMsg = msg
  if (filePaths.value.length > 0) {
    const refs = filePaths.value.map((p) => `[引用文件: ${p}]`).join('\n')
    finalMsg = `${msg}\n\n${refs}`
  }

  emit('send', finalMsg)
  text.value = ''
  filePaths.value = []
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

/* 文件引用标签条 */
.file-refs-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 0 0 8px 0;
}
.file-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 12px;
  color: var(--text-primary);
  max-width: 100%;
  overflow: hidden;
}
.file-tag-icon {
  flex-shrink: 0;
  font-size: 12px;
}
.file-tag-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-tag-remove {
  flex-shrink: 0;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 12px;
  padding: 0 2px;
  line-height: 1;
  transition: color 0.15s;
}
.file-tag-remove:hover {
  color: #c97a7a;
}

.chat-input {
  display: flex;
  align-items: center;
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

/* 添加文件按钮 */
.btn-add-file-wrapper {
  position: relative;
  flex-shrink: 0;
}
.btn-add-file {
  width: 32px;
  height: 32px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  padding: 0;
  font-family: inherit;
}
.btn-add-file:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 8%, transparent);
}
.btn-add-file:disabled {
  opacity: 0.4;
  cursor: default;
}
.btn-add-file-spin {
  display: inline-block;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 添加文件菜单 */
.menu-backdrop {
  position: fixed;
  inset: 0;
  z-index: 99;
}
.add-file-menu {
  position: absolute;
  bottom: calc(100% + 4px);
  left: 0;
  z-index: 100;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  min-width: 140px;
}
.add-file-menu-item {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 8px 14px;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  white-space: nowrap;
  transition: background 0.12s;
}
.add-file-menu-item:hover {
  background: color-mix(in srgb, var(--accent) 12%, transparent);
}
.menu-item-icon {
  font-size: 14px;
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
