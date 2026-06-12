<template>
  <div class="chat-input-wrapper">
    <div v-if="refs.length" class="file-refs-bar">
      <span
        v-for="(r, idx) in refs"
        :key="idx"
        class="file-tag"
        :title="getRefTooltip(r)"
      >
        <span class="file-tag-icon"><Icon :name="getRefIcon(r)" :size="14" /></span>
        <span class="file-tag-name">{{ r.label }}</span>
        <span class="file-tag-source">{{ r.type }}</span>
        <button class="file-tag-remove" @click="removeRef(idx)">✕</button>
      </span>
    </div>
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
      <div class="input-bottom-bar">
        <div class="btn-add-file-wrapper">
          <button class="btn-add-file" :disabled="disabled" @click="toggleMenu">
            <span v-if="loading" class="btn-add-file-spin">⟳</span>
            <Icon v-else name="attach" :size="18" />
          </button>
          <div v-if="showMenu" class="add-file-menu" @click.stop>
            <button class="add-file-menu-item" @click="pickFile">
              <Icon name="menu-file" :size="14" /> 选择文件
            </button>
            <button class="add-file-menu-item" @click="pickFolder">
              <Icon name="menu-folder" :size="14" /> 选择文件夹
            </button>
          </div>
          <div v-if="showMenu" class="menu-backdrop" @click="showMenu = false"></div>
        </div>
        <div class="input-right-group">
          <div class="dropdown">
            <button class="dropdown-trigger" @click.stop="toggleDropdown('provider')">
              {{ selectedProviderId ? (providers.find(p => p.id === selectedProviderId)?.label || selectedProviderId) : '默认模型' }}
              <span class="dropdown-arrow">▾</span>
            </button>
            <div v-if="openDropdown === 'provider'" class="dropdown-menu">
              <button class="dropdown-option" :class="{ selected: !selectedProviderId }" @click="selectProvider('')">默认模型</button>
              <button v-for="p in providers" :key="p.id" class="dropdown-option" :class="{ selected: selectedProviderId === p.id }" @click="selectProvider(p.id)">{{ p.label }}</button>
            </div>
          </div>
          <div v-if="currentModels.length" class="dropdown">
            <button class="dropdown-trigger" @click.stop="toggleDropdown('model')">
              {{ selectedModelName || '选择模型' }}
              <span class="dropdown-arrow">▾</span>
            </button>
            <div v-if="openDropdown === 'model'" class="dropdown-menu">
              <button v-for="m in currentModels" :key="m" class="dropdown-option" :class="{ selected: selectedModelName === m }" @click="selectModel(m)">{{ m }}</button>
            </div>
          </div>
          <div class="input-actions">
            <button
              v-if="!isStreaming"
              class="btn-send"
              :disabled="!text.trim() || disabled"
              @click="handleSend"
            >
              <Icon name="send" :size="16" />
            </button>
            <button v-else class="btn-stop" @click="$emit('stop')">
              <Icon name="stop" :size="12" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { api } from '@/api'
import Icon from '@/components/Icon.vue'
import type { ProviderConfig } from '@/types'
import type { ParsedRef } from '@/utils/references'
import { REF_CHIP_CONFIG } from '@/utils/references'
import { nextTick, onMounted, onUnmounted, ref } from 'vue'

const props = defineProps<{
  isStreaming: boolean
  disabled: boolean
}>()

const emit = defineEmits<{
  send: [text: string, refs: ParsedRef[], providerId?: string, modelName?: string]
  stop: []
  modelChange: [providerId: string, modelName: string]
}>()

const text = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const refs = ref<ParsedRef[]>([])
const loading = ref(false)
const showMenu = ref(false)

// ── 供父组件注入新引用（如 ChatWindow 发出的 cite） ──

function addRef(r: ParsedRef) {
  refs.value.push(r)
}

function removeRef(idx: number) {
  refs.value.splice(idx, 1)
}

/** 从 REF_CHIP_CONFIG 获取图标名 */
function getRefIcon(r: ParsedRef): string {
  return REF_CHIP_CONFIG[r.type]?.icon ?? 'file'
}

/** 从 REF_CHIP_CONFIG 获取 tooltip */
function getRefTooltip(r: ParsedRef): string {
  return REF_CHIP_CONFIG[r.type]?.tooltip(r) ?? r.label
}

defineExpose({ addRef })

// ── LLM 选择器 ──
const providers = ref<ProviderConfig[]>([])
const selectedProviderId = ref('')
const selectedModelName = ref('')
const currentModels = ref<string[]>([])
const openDropdown = ref<'provider' | 'model' | null>(null)

function toggleDropdown(name: 'provider' | 'model') {
  openDropdown.value = openDropdown.value === name ? null : name
}

function selectProvider(id: string) {
  selectedProviderId.value = id
  openDropdown.value = null
  const p = providers.value.find(p => p.id === id)
  currentModels.value = p?.models ?? []
  selectedModelName.value = currentModels.value[0] || ''
  emit('modelChange', selectedProviderId.value, selectedModelName.value)
}

function selectModel(name: string) {
  selectedModelName.value = name
  openDropdown.value = null
  emit('modelChange', selectedProviderId.value, selectedModelName.value)
}

function onDocumentClick() {
  openDropdown.value = null
}
onMounted(() => document.addEventListener('click', onDocumentClick))
onUnmounted(() => document.removeEventListener('click', onDocumentClick))

async function loadProviders() {
  try {
    const res = await api.listProviders()
    providers.value = res.providers.filter(p => p.enabled)
  } catch {
    // 静默失败
  }
}

onMounted(loadProviders)

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
      const refType = type === 'folder' ? 'folder' : 'file'
      refs.value.push({ type: refType, path: data.path, label: getFileName(data.path) } as ParsedRef)
    }
  } catch {
    // 静默失败
  } finally {
    loading.value = false
  }
}

function handleSend() {
  const msg = text.value.trim()
  if (!msg || props.disabled) return

  emit('send', msg, refs.value, selectedProviderId.value || undefined, selectedModelName.value || undefined)
  text.value = ''
  refs.value = []
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
  padding: 12px 24px 16px;
  background: var(--bg-card);
}

/* ── 自定义 Dropdown ── */
.dropdown {
  position: relative;
  display: inline-block;
}
.dropdown-trigger {
  font-size: 11px;
  padding: 3px 6px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  white-space: nowrap;
  transition: background 0.15s, color 0.15s;
  display: flex;
  align-items: center;
  gap: 3px;
  max-width: 110px;
}
.dropdown-trigger:hover {
  background: var(--bg-secondary);
  color: var(--text-primary);
}
.dropdown-arrow {
  font-size: 9px;
  line-height: 1;
  opacity: 0.6;
}
.dropdown-menu {
  position: absolute;
  bottom: calc(100% + 4px);
  right: 0;
  z-index: 200;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  min-width: 140px;
  max-height: 200px;
  overflow-y: auto;
  padding: 4px;
}
.dropdown-option {
  display: block;
  width: 100%;
  text-align: left;
  padding: 6px 10px;
  border: none;
  border-radius: 5px;
  background: transparent;
  color: #374151;
  font-size: 12px;
  cursor: pointer;
  font-family: inherit;
  white-space: nowrap;
  transition: background 0.1s;
}
.dropdown-option:hover {
  background: #f3f4f6;
}
.dropdown-option.selected {
  color: #000000;
  font-weight: 600;
  background: #f9fafb;
}

/* 引用标签条 */
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
.file-tag-source {
  font-size: 10px;
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 10%, transparent);
  padding: 0 5px;
  border-radius: 3px;
  flex-shrink: 0;
}

.chat-input {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 10px 14px 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  transition: border-color 0.2s, box-shadow 0.2s;
}
.chat-input:focus-within {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent) 10%, transparent);
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
.input-area {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 15px;
  line-height: 1.6;
  color: var(--text-primary);
  resize: none;
  font-family: inherit;
  min-height: 24px;
}
.input-area::placeholder {
  color: #9ca3af;
}
.input-bottom-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.input-right-group {
  display: flex;
  align-items: center;
  gap: 4px;
}
.input-actions {
  display: flex;
  gap: 6px;
  align-items: center;
}
.btn-send,
.btn-stop {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  font-size: 16px;
  cursor: pointer;
  transition: background 0.15s, opacity 0.15s;
  font-family: inherit;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.btn-send {
  background: var(--accent);
  color: #fff;
}
.btn-send:hover:not(:disabled) {
  background: #1d4ed8;
}
.btn-send:disabled {
  opacity: 0.35;
  cursor: default;
}
.btn-stop {
  background: #ef4444;
  color: #fff;
  font-size: 12px;
}
.btn-stop:hover {
  background: #dc2626;
}
</style>
