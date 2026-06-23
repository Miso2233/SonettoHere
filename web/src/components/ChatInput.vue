<template>
  <div class="chat-input-wrapper">
    <div v-if="showLinkInput" class="link-input-bar">
      <input
        ref="linkInputRef"
        v-model="linkUrl"
        type="url"
        class="link-input"
        placeholder="输入链接 URL……"
        @keydown.enter.prevent="confirmLink"
        @keydown.escape.prevent="cancelLink"
      />
      <button class="link-input-confirm" :disabled="!linkUrl.trim()" @click="confirmLink">✓</button>
      <button class="link-input-cancel" @click="cancelLink">✕</button>
    </div>
    <div
      ref="inputContainerRef"
      class="chat-input"
      :class="{ 'is-resizing': isResizing }"
      :style="containerStyle"
    >
      <div
        class="resize-handle"
        @pointerdown="startResize"
        title="拖拽调整输入框高度"
      >
        <div class="resize-handle-grip"></div>
      </div>
      <TransitionGroup name="ref-tag" tag="div" class="file-refs-bar" @before-leave="freezeLeavePos">
        <span
          v-for="(r, idx) in refs"
          :key="r.type + r.label + idx"
          class="file-tag"
          :class="{ blocked: 'blocked' in r && r.blocked }"
          :title="getRefTooltip(r)"
        >
          <span class="file-tag-icon"><Icon :name="getRefIcon(r)" :size="14" /></span>
          <span class="file-tag-name">{{ r.label }}</span>
          <span class="file-tag-source">{{ r.type }}</span>
          <span v-if="'blocked' in r && r.blocked" class="file-tag-blocked">blocked</span>
          <button class="file-tag-remove" @click="removeRef(idx)">✕</button>
        </span>
      </TransitionGroup>
      <div class="input-body">
        <textarea
          ref="textareaRef"
          v-model="text"
          class="input-area"
          placeholder="输入消息…… @技能 · #工具 · !宏"
          :disabled="disabled"
          rows="1"
          @keydown="onKeydown"
          @input="autoResize"
          @paste="onPaste"
        ></textarea>
      </div>
      <hr class="input-divider" />
      <div class="input-bottom-bar">
        <div class="input-left-group">
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
            <button class="add-file-menu-item" @click="startLinkInput">
              <Icon name="link" :size="14" /> 加入链接
            </button>
          </div>
          <div v-if="showMenu" class="menu-backdrop" @click="showMenu = false"></div>
          </div>
        </div>
        <div class="input-right-group">
          <div class="dropdown">
            <button class="dropdown-trigger" :class="{ empty: providers.length === 0 }" @click.stop="toggleDropdown('provider')">
              {{ providers.length === 0 ? '未配置模型' : (providers.find(p => p.id === selectedProviderId)?.label || '选择提供商') }}
              <span class="dropdown-arrow">▾</span>
            </button>
            <div v-if="openDropdown === 'provider'" class="dropdown-menu">
              <button v-if="providers.length === 0" class="dropdown-option disabled">暂无可用的提供商，请先在模型设置中添加</button>
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
              :disabled="!text.trim() || disabled || noProvider"
              :title="noProvider ? '请先在模型设置中添加 LLM 提供商' : ''"
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
    <AutocompletePanel
      :items="acFiltered"
      :visible="acMode !== null"
      :position="acPosition"
      :active-index="acActiveIndex"
      :filter-text="acFilterText"
      :icon-name="acMode === 'tool' ? 'tool' : 'sparkles'"
      @select="confirmItem"
      @close="acMode = null"
      @update:active-index="acActiveIndex = $event"
    />
  </div>
</template>

<script setup lang="ts">
import { api } from '@/api'
import AutocompletePanel from '@/components/AutocompletePanel.vue'
import Icon from '@/components/Icon.vue'
import type { ProviderConfig, SkillInfo, ToolInfo } from '@/types'
import type { ParsedRef } from '@/utils/references'
import { REF_CHIP_CONFIG } from '@/utils/references'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

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
const inputContainerRef = ref<HTMLDivElement | null>(null)
const refs = ref<ParsedRef[]>([])
const loading = ref(false)
const showMenu = ref(false)
const showLinkInput = ref(false)
const linkUrl = ref('')
const linkInputRef = ref<HTMLInputElement | null>(null)

// ── 供父组件注入新引用（如 ChatWindow 发出的 cite） ──

function addRef(r: ParsedRef) {
  refs.value.push(r)
}

function removeRef(idx: number) {
  refs.value.splice(idx, 1)
}

/** TransitionGroup before-leave：冻结退场元素的位置，使其脱离 flex 流而不跳跃 */
function freezeLeavePos(el: Element) {
  const htmlEl = el as HTMLElement
  const parent = htmlEl.offsetParent as HTMLElement
  if (parent) {
    htmlEl.style.left = htmlEl.offsetLeft + 'px'
    htmlEl.style.top = htmlEl.offsetTop + 'px'
  }
}

/** 从 REF_CHIP_CONFIG 获取图标名 */
function getRefIcon(r: ParsedRef): string {
  return REF_CHIP_CONFIG[r.type]?.icon ?? 'file'
}

/** 从 REF_CHIP_CONFIG 获取 tooltip，受阻时附加原因 */
function getRefTooltip(r: ParsedRef): string {
  const base = REF_CHIP_CONFIG[r.type]?.tooltip(r) ?? r.label
  if ('blocked' in r && r.blocked) {
    return `${base}\n⛔ ${r.blockedReason || '路径被阻挡，无法访问'}`
  }
  return base
}

defineExpose({ addRef })

// ── 链接引用 ──

const LINK_RE = /^https?:\/\/[^\s/$.?#].[^\s]*$/i

function startLinkInput() {
  showMenu.value = false
  linkUrl.value = ''
  showLinkInput.value = true
  nextTick(() => linkInputRef.value?.focus())
}

function confirmLink() {
  const url = linkUrl.value.trim()
  if (!url) return
  // 如果没有协议前缀，自动补 https://
  const normalized = /^https?:\/\//i.test(url) ? url : 'https://' + url
  if (!LINK_RE.test(normalized)) return
  try {
    const domain = new URL(normalized).hostname.replace(/^www\./, '')
    refs.value.push({ type: 'web_link', url: normalized, label: domain, domain })
    linkUrl.value = ''
    showLinkInput.value = false
  } catch {
    // URL 解析失败，不做操作
  }
}

function cancelLink() {
  linkUrl.value = ''
  showLinkInput.value = false
}

// ── 粘贴URL自动识别 ──

/** 判断文本是否看起来像域名/IP，适合补 https:// */
function looksLikeHost(text: string): boolean {
  // 允许 localhost、带点的域名、IPv4、IPv6
  return /^[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)+(:[0-9]+)?(\/|$)/.test(text)
      || /^localhost(:[0-9]+)?(\/|$)/i.test(text)
}

function onPaste(e: ClipboardEvent) {
  const text = e.clipboardData?.getData('text/plain')?.trim()
  if (!text) return

  // 已有协议头 → 直接校验完整 URL
  if (/^https?:\/\//i.test(text)) {
    try {
      const url = new URL(text)
      if (['http:', 'https:'].includes(url.protocol) && url.hostname.includes('.')) {
        e.preventDefault()
        const domain = url.hostname.replace(/^www\./, '')
        refs.value.push({ type: 'web_link', url: text, label: domain, domain } as ParsedRef)
      }
    } catch { /* 走默认粘贴 */ }
    return
  }

  // 无协议头 → 仅当看起来像域名时才补 https:// 并二次校验
  if (looksLikeHost(text)) {
    const normalized = 'https://' + text
    try {
      const url = new URL(normalized)
      if (['http:', 'https:'].includes(url.protocol)) {
        e.preventDefault()
        const domain = url.hostname.replace(/^www\./, '')
        refs.value.push({ type: 'web_link', url: normalized, label: domain, domain } as ParsedRef)
      }
    } catch { /* 走默认粘贴 */ }
  }
}

// ── @ / # 自动补全（统一状态机） ──

type AcMode = 'skill' | 'tool' | 'macro' | null

const acMode = ref<AcMode>(null)
const acFilterText = ref('')
const acPosition = ref({ x: 0, y: 0 })
const acActiveIndex = ref(0)
const acTriggerPos = ref(-1)
const acTriggerChar = ref('')

const skills = ref<SkillInfo[]>([])
const tools = ref<ToolInfo[]>([])
const macros = ref<SkillInfo[]>([])

/** 当前模式对应的数据源 */
const acSource = computed(() =>
  acMode.value === 'skill' ? skills.value
  : acMode.value === 'tool' ? tools.value
  : acMode.value === 'macro' ? macros.value
  : []
)

/** 筛选 + 排序后的候选项 */
const acFiltered = computed(() => {
  const src = acSource.value
  if (!acFilterText.value) return src
  const lower = acFilterText.value.toLowerCase()

  const scored = src
    .map(item => {
      const nameLower = item.name.toLowerCase()
      if (!nameLower.includes(lower)) return null
      const prefix = nameLower.startsWith(lower)
      const count = prefix ? 1 : nameLower.split(lower).length - 1
      const score = prefix ? 4 : 2
      return { item, score, count }
    })
    .filter((x): x is NonNullable<typeof x> => x !== null)

  scored.sort((a, b) => {
    if (a.score !== b.score) return b.score - a.score
    if (a.count !== b.count) return b.count - a.count
    return a.item.name.localeCompare(b.item.name)
  })

  return scored.map(s => s.item)
})

async function loadSkills() {
  try {
    const res = await api.listSkills()
    skills.value = res.skills
  } catch (e) {
    console.error('[ChatInput] 加载技能失败:', e)
  }
}

async function loadTools() {
  try {
    const res = await api.listTools()
    tools.value = res.tools
  } catch (e) {
    console.error('[ChatInput] 加载工具失败:', e)
  }
}

async function loadMacros() {
  try {
    const res = await api.listMacros()
    macros.value = res.macros
  } catch (e) {
    console.error('[ChatInput] 加载宏失败:', e)
  }
}

/** 检测 @ / # 触发 */
watch(text, () => {
  const el = textareaRef.value
  if (!el || el !== document.activeElement) return
  const val = text.value
  const cursorPos = el.selectionStart
  const textBeforeCursor = val.slice(0, cursorPos)

  // 检查 @、#、!、！，取最近者
  let triggerPos = -1
  let triggerChar = ''
  for (const ch of ['@', '#', '!', '！'] as const) {
    const idx = textBeforeCursor.lastIndexOf(ch)
    if (idx > triggerPos) {
      triggerPos = idx
      triggerChar = ch
    }
  }

  const mode: AcMode = triggerChar === '@' ? 'skill' : triggerChar === '#' ? 'tool' : (triggerChar === '!' || triggerChar === '！') ? 'macro' : null

  if (triggerPos !== -1 && mode) {
    const after = textBeforeCursor.slice(triggerPos + 1)
    const charBefore = triggerPos === 0 ? ' ' : textBeforeCursor[triggerPos - 1]
    if (!/\w/.test(charBefore)) {
      acMode.value = mode
      acFilterText.value = after
      acTriggerPos.value = triggerPos
      acTriggerChar.value = triggerChar
      acActiveIndex.value = 0
      acPosition.value = calcCursorPixelPos(el, cursorPos)
      return
    }
  }
  acMode.value = null
})

function onKeydown(e: KeyboardEvent) {
  if (acMode.value) {
    const len = acFiltered.value.length
    if (e.key === 'Tab') {
      e.preventDefault()
      confirmItem()
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      acActiveIndex.value = ((acActiveIndex.value - 1) % len + len) % len
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      acActiveIndex.value = (acActiveIndex.value + 1) % len
      return
    }
    if (e.key === 'Escape') {
      acMode.value = null
      return
    }
  }

  // Enter 发送（仅当面板未打开时）
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

function confirmItem() {
  const item = acFiltered.value[acActiveIndex.value]
  if (!item) return

  // 移除触发符及后续文本
  const el = textareaRef.value
  const cursorPos = el?.selectionStart ?? text.value.length
  text.value = text.value.slice(0, acTriggerPos.value) + text.value.slice(cursorPos)

  // 创建对应类型的引用
  const ref: ParsedRef =
    acMode.value === 'skill' ? { type: 'skill', name: item.name, label: item.name }
    : acMode.value === 'macro' ? { type: 'macro', name: item.name, label: item.name }
    : { type: 'tool', name: item.name, label: item.name }
  refs.value.push(ref)

  acMode.value = null
  nextTick(() => autoResize())
}

function calcCursorPixelPos(textarea: HTMLTextAreaElement, pos: number): { x: number; y: number } {
  const style = getComputedStyle(textarea)
  const mirror = document.createElement('div')
  mirror.style.cssText = `
    position: fixed; top: 0; left: -9999px; visibility: hidden; white-space: pre-wrap;
    word-wrap: break-word; overflow-wrap: break-word;
    font: ${style.font}; font-size: ${style.fontSize};
    letter-spacing: ${style.letterSpacing};
    width: ${textarea.clientWidth}px;
    padding: ${style.padding};
  `
  mirror.textContent = textarea.value.slice(0, pos) + '.'
  document.body.appendChild(mirror)

  const textareaRect = textarea.getBoundingClientRect()
  const mirrorRect = mirror.getBoundingClientRect()
  const lineHeight = parseInt(style.lineHeight) || 24

  // 计算光标所在行相对于 mirror 顶部的位置
  const lines = mirror.textContent!.split('\n')
  const lastLine = lines[lines.length - 1]
  const linePixel = (lines.length - 1) * lineHeight

  // 用 span 精确测量最后一行的宽度
  const span = document.createElement('span')
  span.textContent = lastLine
  span.style.cssText = `visibility: hidden; white-space: pre; font: ${style.font}; font-size: ${style.fontSize};`
  document.body.appendChild(span)

  const x = textareaRect.left + span.getBoundingClientRect().width + parseInt(style.paddingLeft || '0') - 8
  const y = textareaRect.top + mirrorRect.height - textarea.scrollTop + 4

  document.body.removeChild(mirror)
  document.body.removeChild(span)

  return { x, y }
}

// ── LLM 选择器 ──
const providers = ref<ProviderConfig[]>([])
const selectedProviderId = ref('')
const selectedModelName = ref('')
const currentModels = ref<string[]>([])
const openDropdown = ref<'provider' | 'model' | null>(null)
const noProvider = computed(() => providers.value.length === 0)

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
    // 默认选中第一个已启用的提供商
    if (providers.value.length > 0 && !selectedProviderId.value) {
      selectProvider(providers.value[0].id)
    }
  } catch {
    // 静默失败
  }
}

onMounted(loadProviders)
onMounted(loadSkills)
onMounted(loadTools)
onMounted(loadMacros)

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

async function _pick(type: 'file' | 'folder') {
  if (loading.value) return
  loading.value = true
  try {
    const data = await api.selectFile(type)
    if (data.path) {
      const refType = type === 'folder' ? 'folder' : 'file'
      const idx = refs.value.length
      refs.value.push({ type: refType, path: data.path, label: getFileName(data.path) } as ParsedRef)
      console.log('[ChatInput] _pick: pushed ref idx=%d type=%s path=%s', idx, refType, data.path)

      // 异步检查路径是否被拒止锚或白名单阻挡
      api.checkPathBlocked(data.path).then(result => {
        console.log('[ChatInput] checkPathBlocked result for', data.path, result)
        if (result.blocked) {
          // 通过 refs.value[idx] 操作以触发响应式更新
          const entry = refs.value[idx] as any
          entry.blocked = true
          entry.blockedReason = result.reason
          console.log('[ChatInput] marked ref %d as blocked, reason: %s', idx, result.reason)
        }
      }).catch(err => {
        console.warn('[ChatInput] checkPathBlocked failed:', err)
      })
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
  // 如果用户手动拖拽过容器高度，不干涉 textarea 高度，交由 flex 布局自动填充
  if (customHeight.value !== null) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 160) + 'px'
}

// ── 拖拽调整输入框高度 ──

const customHeight = ref<number | null>(null)
const isResizing = ref(false)
const resizeStartY = ref(0)
const resizeStartHeight = ref(0)
const handleRef = ref<HTMLDivElement | null>(null)
const DEFAULT_INPUT_HEIGHT = 117
const initialHeight = ref(DEFAULT_INPUT_HEIGHT)

const containerStyle = computed(() => {
  const minHeight = initialHeight.value + 'px'
  if (customHeight.value === null) return { minHeight }
  return { height: customHeight.value + 'px', minHeight }
})

/** 组件挂载后捕获输入框的初始默认高度，作为拖拽下限 */
onMounted(() => {
  nextTick(() => {
    const el = inputContainerRef.value
    if (el) initialHeight.value = Math.max(DEFAULT_INPUT_HEIGHT, el.clientHeight)
  })
})

function startResize(e: PointerEvent) {
  const handle = e.currentTarget as HTMLDivElement
  handle.setPointerCapture(e.pointerId)
  handleRef.value = handle

  isResizing.value = true
  resizeStartY.value = e.clientY
  const el = inputContainerRef.value
  resizeStartHeight.value = el ? el.clientHeight : initialHeight.value
  if (customHeight.value === null) {
    customHeight.value = resizeStartHeight.value
  }

  // 拖拽时清除 textarea 行内高度，让 CSS height: 100% 接管以填充容器
  if (textareaRef.value) textareaRef.value.style.height = ''

  handle.addEventListener('pointermove', onResizeMove)
  handle.addEventListener('pointerup', onResizeEnd)
  handle.addEventListener('pointercancel', onResizeEnd)
}

function onResizeMove(e: PointerEvent) {
  const delta = resizeStartY.value - e.clientY
  const newHeight = Math.max(initialHeight.value, Math.min(600, resizeStartHeight.value + delta))
  customHeight.value = newHeight
}

function onResizeEnd(e: PointerEvent) {
  isResizing.value = false
  const handle = handleRef.value
  if (handle) {
    handle.releasePointerCapture(e.pointerId)
    handle.removeEventListener('pointermove', onResizeMove)
    handle.removeEventListener('pointerup', onResizeEnd)
    handle.removeEventListener('pointercancel', onResizeEnd)
    handleRef.value = null
  }
}
</script>

<style scoped>
.chat-input-wrapper {
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
  padding: 4px 8px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  white-space: nowrap;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  gap: 4px;
  max-width: 110px;
}
.dropdown-trigger:hover {
  border-color: var(--border);
  background: var(--bg-secondary);
  color: var(--text-primary);
}
.dropdown-trigger.empty {
  color: var(--status-error);
  opacity: 0.7;
}
.dropdown-option.disabled {
  color: var(--text-secondary);
  font-style: italic;
  cursor: default;
  font-size: 11px;
  white-space: normal;
  line-height: 1.4;
}
.dropdown-arrow {
  font-size: 8px;
  line-height: 1;
  opacity: 0.5;
}
.dropdown-menu {
  position: absolute;
  bottom: calc(100% + 4px);
  right: 0;
  z-index: 200;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: var(--shadow-lg);
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
  gap: 5px;
  padding: 10px 14px 0;
}
.file-refs-bar:empty {
  display: none;
}
.file-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px 2px 6px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 100px;
  font-size: 11px;
  color: var(--text-primary);
  max-width: 100%;
  overflow: hidden;
  transition: border-color 0.15s, background 0.15s;
}
.file-tag:hover {
  border-color: var(--accent-light);
  background: var(--bg-primary);
}
.file-tag-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
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
  color: var(--status-error);
}
.file-tag-source {
  font-size: 9px;
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--accent) 6%, transparent);
  padding: 1px 6px;
  border-radius: 100px;
  flex-shrink: 0;
  letter-spacing: 0.3px;
  text-transform: uppercase;
}
.file-tag-blocked {
  font-size: 9px;
  color: var(--status-error);
  background: #fee2e2;
  padding: 0 5px;
  border-radius: 3px;
  flex-shrink: 0;
  font-weight: 600;
}
.file-tag.blocked {
  border-color: var(--status-error);
  background: #fef2f2;
}
.file-tag.blocked .file-tag-name {
  color: var(--status-error);
}

/* ── 输入区主体 ── */
.input-body {
  flex: 1;
  min-height: 0;
  padding: 10px 14px 0;
}

/* 过渡分隔线 */
.input-divider {
  margin: 6px 14px 0;
  border: none;
  height: 1px;
  background: var(--border);
  opacity: 0.6;
  transition: opacity 0.2s;
}
.chat-input:focus-within .input-divider {
  opacity: 1;
}

/* TransitionGroup 动画：从下往上缓出弹出，退场缩小淡出 */
.ref-tag-enter-active {
  transition: all 0.25s ease-out;
}
.ref-tag-enter-from {
  opacity: 0;
  transform: translateY(12px);
}
.ref-tag-leave-active {
  transition: all 0.2s ease-in;
  position: absolute !important;
}
.ref-tag-leave-to {
  opacity: 0;
  transform: translateY(12px);
}
.ref-tag-move {
  transition: transform 0.25s ease-out;
}

/* 链接输入条 */
.link-input-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 0 8px 0;
  max-width: 768px;
  margin: 0 auto;
}
.link-input {
  flex: 1;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 13px;
  background: var(--bg-primary);
  color: var(--text-primary);
  outline: none;
  font-family: inherit;
  transition: border-color 0.15s;
}
.link-input:focus {
  border-color: var(--accent);
}
.link-input::placeholder {
  color: #9ca3af;
}
.link-input-confirm,
.link-input-cancel {
  width: 28px;
  height: 28px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  transition: all 0.12s;
  flex-shrink: 0;
}
.link-input-confirm:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
}
.link-input-confirm:disabled {
  opacity: 0.4;
  cursor: default;
}
.link-input-cancel:hover {
  border-color: #c97a7a;
  color: #c97a7a;
}

/* 拖拽调整手柄 */
.resize-handle {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 12px;
  cursor: ns-resize;
  user-select: none;
  touch-action: none;
  flex-shrink: 0;
  margin-top: -2px;
}
.resize-handle-grip {
  width: 32px;
  height: 3px;
  border-radius: 2px;
  background: var(--border);
  transition: background 0.15s, width 0.2s;
  opacity: 0.5;
}
.resize-handle:hover .resize-handle-grip {
  background: var(--accent);
  width: 56px;
  opacity: 1;
}

.chat-input {
  display: flex;
  flex-direction: column;
  max-width: 768px;
  margin: 0 auto;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 0;
  box-shadow: var(--shadow-soft);
  transition: border-color 0.2s, box-shadow 0.2s;
  overflow: visible;
}
.chat-input.is-resizing {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent) 20%, transparent);
}
.chat-input:focus-within {
  border-color: var(--accent);
  box-shadow: var(--shadow-soft), 0 0 0 1px color-mix(in srgb, var(--accent) 10%, transparent);
}

/* 添加文件按钮 */
.btn-add-file-wrapper {
  position: relative;
  flex-shrink: 0;
  z-index: 210;
}
.btn-add-file {
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  padding: 0;
  font-family: inherit;
  font-size: 17px;
  line-height: 1;
}
.btn-add-file:hover:not(:disabled) {
  background: var(--bg-secondary);
  color: var(--text-primary);
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
  box-shadow: var(--shadow-lg);
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
  width: 100%;
  height: 100%;
  border: none;
  outline: none;
  background: transparent;
  font-size: 15px;
  line-height: 1.6;
  color: var(--text-primary);
  resize: none;
  font-family: inherit;
  min-height: 24px;
  max-height: 160px;
  overflow-y: auto;
  padding: 4px 2px 4px 10px;
}
.input-area::placeholder {
  color: #9ca3af;
}
.input-bottom-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 10px 6px 14px;
}
.input-left-group {
  display: flex;
  align-items: center;
  gap: 2px;
}
.input-right-group {
  display: flex;
  align-items: center;
  gap: 6px;
}
.input-actions {
  display: flex;
  gap: 4px;
  align-items: center;
}
.btn-send,
.btn-stop {
  width: 34px;
  height: 34px;
  border: none;
  border-radius: 50%;
  font-size: 15px;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
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
  transform: scale(1.08);
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
.btn-send:active:not(:disabled) {
  transform: scale(0.95);
}
.btn-send:disabled {
  opacity: 0.3;
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
