<template>
  <div class="studio-form">
    <div class="form-section">
      <label class="form-label">名称</label>
      <p class="form-hint">工作坊展示名，同时作为文件名（保存后用于下拉选择与提示词注入）</p>
      <input
        class="input"
        :value="nameValue"
        placeholder="如：本地 Obsidian 知识管理工作坊"
        @input="writeName(($event.target as HTMLInputElement).value)"
      />
    </div>

    <div v-for="spec in schema" :key="spec.key" class="form-section">
      <label class="form-label">{{ spec.label }}</label>
      <p v-if="spec.description" class="form-hint">{{ spec.description }}</p>

      <!-- text -->
      <input
        v-if="spec.kind === 'text'"
        class="input"
        :value="readPath(model, spec.key) ?? ''"
        @input="writePath(model, spec.key, ($event.target as HTMLInputElement).value)"
      />

      <!-- code -->
      <textarea
        v-else-if="spec.kind === 'code'"
        class="input mono"
        rows="6"
        :value="readPath(model, spec.key) ?? ''"
        @input="writePath(model, spec.key, ($event.target as HTMLTextAreaElement).value)"
      ></textarea>

      <!-- list -->
      <template v-else-if="spec.kind === 'list'">
        <template v-if="spec.item_key && spec.item_note">
          <div v-for="(item, i) in listArray(spec.key)" :key="i" class="list-row folder-row">
            <input
              class="input mono"
              :value="item[spec.item_key] ?? ''"
              :placeholder="spec.item_key"
              @input="item[spec.item_key] = ($event.target as HTMLInputElement).value"
            />
            <div class="folder-row-bottom">
              <input
                class="input"
                :value="item[spec.item_note] ?? ''"
                :placeholder="spec.item_note"
                @input="item[spec.item_note] = ($event.target as HTMLInputElement).value"
              />
              <button
                v-if="spec.item_key === 'path'"
                type="button"
                class="btn folder-pick"
                :disabled="picking"
                @click="pickFolder(spec, i)"
              >
                <Icon name="menu-folder" :size="14" /> 选择文件夹
              </button>
              <button type="button" class="row-x" @click="removeAt(spec.key, i)" title="删除">&times;</button>
            </div>
          </div>
          <p v-if="listArray(spec.key).length === 0" class="form-empty">（无）</p>
        </template>
        <template v-else>
          <div v-for="(item, i) in listArray(spec.key)" :key="i" class="list-row">
            <input
              class="input"
              :value="item"
              @input="setAt(spec.key, i, ($event.target as HTMLInputElement).value)"
            />
            <button type="button" class="row-x" @click="removeAt(spec.key, i)" title="删除">&times;</button>
          </div>
          <p v-if="listArray(spec.key).length === 0" class="form-empty">（无）</p>
        </template>
        <button type="button" class="btn sm" @click="addListRow(spec)">+ 添加</button>
      </template>

      <!-- join：输入即按字段数据源过滤，回车/Tab 添加 -->
      <div v-else-if="spec.kind === 'join'" class="join-field">
        <div class="chips">
          <span v-for="(t, i) in joinArray(spec.key)" :key="i" class="chip">
            {{ t }}
            <button type="button" class="chip-x" @click="removeAt(spec.key, i)">×</button>
          </span>
          <input
            class="input chip-input"
            :value="drafts[spec.key] ?? ''"
            placeholder="输入过滤，回车/Tab 添加"
            @focus="onJoinFocus(spec, $event)"
            @input="onJoinInput(spec, $event)"
            @keydown="onJoinKeydown(spec, $event)"
          />
        </div>
        <AutocompletePanel
          :items="acFiltered"
          :visible="acSpec === spec"
          :position="acPosition"
          :active-index="acActiveIndex"
          :filter-text="drafts[spec.key] ?? ''"
          :icon-name="spec.key === 'tools' ? 'tool' : 'sparkles'"
          placement="bottom"
          @select="confirmJoin(spec)"
          @close="closeAc"
          @update:active-index="acActiveIndex = $event"
        />
      </div>

      <!-- keyval -->
      <template v-else-if="spec.kind === 'keyval'">
        <div v-for="(row, i) in keyRows[spec.key] ?? []" :key="i" class="list-row">
          <input
            class="input mono list-path"
            :value="row.k"
            placeholder="键"
            @input="updateKeyRow(spec.key, i, 'k', ($event.target as HTMLInputElement).value)"
          />
          <input
            class="input list-note"
            :value="row.v"
            placeholder="值"
            @input="updateKeyRow(spec.key, i, 'v', ($event.target as HTMLInputElement).value)"
          />
          <button type="button" class="row-x" @click="removeKeyRow(spec.key, i)" title="删除">&times;</button>
        </div>
        <p v-if="(keyRows[spec.key] ?? []).length === 0" class="form-empty">（无）</p>
        <button type="button" class="btn sm" @click="addKeyRow(spec.key)">+ 添加</button>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { api } from '@/api'
import AutocompletePanel from '@/components/AutocompletePanel.vue'
import Icon from '@/components/Icon.vue'
import type { SkillInfo, StudioDocument, StudioFieldSpec, ToolInfo } from '@/types'
import { filterAndScore } from '@/utils/autocomplete'
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'

const props = defineProps<{
  model: StudioDocument
  schema: StudioFieldSpec[]
}>()

/** 按点路径取值（body.* 嵌套）；缺失返回 undefined */
function readPath(obj: any, key: string): any {
  let cur = obj
  for (const part of key.split('.')) {
    if (cur == null || typeof cur !== 'object') return undefined
    cur = cur[part]
  }
  return cur
}

/** 按点路径写值；中间对象缺失时自动创建 */
function writePath(obj: any, key: string, val: any) {
  const parts = key.split('.')
  let cur = obj
  for (let i = 0; i < parts.length - 1; i++) {
    const p = parts[i]
    if (cur[p] == null || typeof cur[p] !== 'object' || Array.isArray(cur[p])) {
      cur[p] = {}
    }
    cur = cur[p]
  }
  cur[parts[parts.length - 1]] = val
}

// ── 名称（schema 不含 name，单独处理） ──
const nameValue = computed(() => (props.model.name as string | undefined) ?? '')
function writeName(v: string) {
  props.model.name = v
}

// ── list ──
function listArray(key: string): any[] {
  const v = readPath(props.model, key)
  return Array.isArray(v) ? v : []
}

function ensureArray(key: string): any[] {
  if (!Array.isArray(readPath(props.model, key))) {
    writePath(props.model, key, [])
  }
  return listArray(key)
}

function addListRow(spec: StudioFieldSpec) {
  const arr = ensureArray(spec.key)
  if (spec.item_key && spec.item_note) {
    arr.push({ [spec.item_key]: '', [spec.item_note]: '' })
  } else {
    arr.push('')
  }
}

function removeAt(key: string, i: number) {
  const arr = listArray(key)
  if (i >= 0 && i < arr.length) arr.splice(i, 1)
}

function setAt(key: string, i: number, v: string) {
  const arr = listArray(key)
  if (i >= 0 && i < arr.length) arr[i] = v
}

// ── 文件夹选取（复用聊天框/白名单页的系统文件夹选择器） ──
const picking = ref(false)

async function pickFolder(spec: StudioFieldSpec, i: number) {
  const arr = listArray(spec.key)
  if (i < 0 || i >= arr.length || !arr[i]) return
  picking.value = true
  try {
    const res = await api.selectFolder()
    if (res.path && spec.item_key) {
      arr[i][spec.item_key] = res.path
    }
  } catch {
    /* 静默 */
  } finally {
    picking.value = false
  }
}

// ── join（标签 chips + 提词补全，复用聊天框体系） ──
const drafts = reactive<Record<string, string>>({})

const toolSource = ref<ToolInfo[]>([])
const macroSource = ref<SkillInfo[]>([])
const skillSource = ref<SkillInfo[]>([])

const acSpec = ref<StudioFieldSpec | null>(null)
const acActiveIndex = ref(0)
const acPosition = ref({ x: 0, y: 0 })

/** 该 join 字段对应的数据源（工具/宏/技能） */
function sourceFor(spec: StudioFieldSpec) {
  return spec.key === 'tools' ? toolSource.value
    : spec.key === 'macros' ? macroSource.value
    : spec.key === 'skills' ? skillSource.value
    : []
}

/** 当前补全面板的候选项（按输入过滤，复用聊天框评分逻辑） */
const acFiltered = computed(() => {
  if (!acSpec.value) return []
  return filterAndScore(sourceFor(acSpec.value), drafts[acSpec.value.key] ?? '')
})

function joinArray(key: string): string[] {
  const v = readPath(props.model, key)
  return Array.isArray(v) ? v : []
}

function pushUnique(arr: any[], name: string) {
  if (name && !arr.includes(name)) arr.push(name)
}

function openAc(spec: StudioFieldSpec, el: HTMLInputElement) {
  acSpec.value = spec
  acActiveIndex.value = 0
  const r = el.getBoundingClientRect()
  acPosition.value = { x: r.left, y: r.bottom }
}

function closeAc() {
  acSpec.value = null
  acActiveIndex.value = 0
}

function onJoinFocus(spec: StudioFieldSpec, e: FocusEvent) {
  if ((drafts[spec.key] ?? '').trim()) openAc(spec, e.target as HTMLInputElement)
  else closeAc()
}

function onJoinInput(spec: StudioFieldSpec, e: Event) {
  const el = e.target as HTMLInputElement
  drafts[spec.key] = el.value
  if (el.value.trim()) openAc(spec, el)
  else closeAc()
}

function onJoinKeydown(spec: StudioFieldSpec, e: KeyboardEvent) {
  const isOwner = acSpec.value === spec
  const len = acFiltered.value.length
  if (isOwner && len > 0) {
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      acActiveIndex.value = (acActiveIndex.value - 1 + len) % len
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      acActiveIndex.value = (acActiveIndex.value + 1) % len
      return
    }
    if (e.key === 'Tab') {
      e.preventDefault()
      confirmJoin(spec)
      return
    }
  }
  if (e.key === 'Escape') {
    closeAc()
    return
  }
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    if (isOwner && len > 0) confirmJoin(spec)
    else addJoinRaw(spec)
  }
}

function confirmJoin(spec: StudioFieldSpec) {
  const item = acFiltered.value[acActiveIndex.value]
  if (item) pushUnique(ensureArray(spec.key), item.name)
  drafts[spec.key] = ''
  closeAc()
}

function addJoinRaw(spec: StudioFieldSpec) {
  const v = (drafts[spec.key] ?? '').trim()
  if (!v) return
  pushUnique(ensureArray(spec.key), v)
  drafts[spec.key] = ''
}

/** 焦点移出 join 字段时关闭补全（面板项为不可聚焦 div，点击不会触发 focusin） */
function onDocumentFocusIn(e: FocusEvent) {
  const t = e.target as HTMLElement | null
  if (!t || !t.closest('.join-field')) closeAc()
}

async function loadJoinSources() {
  try {
    toolSource.value = (await api.listTools()).tools
  } catch { /* 静默 */ }
  try {
    macroSource.value = (await api.listMacros()).macros
  } catch { /* 静默 */ }
  try {
    skillSource.value = (await api.listSkills()).skills
  } catch { /* 静默 */ }
}

// ── keyval（键值对行，就地同步回 dict） ──
const keyRows = reactive<Record<string, { k: string; v: string }[]>>({})

function rowsFromDict(key: string): { k: string; v: string }[] {
  const d = readPath(props.model, key)
  if (d && typeof d === 'object' && !Array.isArray(d)) {
    return Object.entries(d).map(([k, v]) => ({ k, v: String(v ?? '') }))
  }
  return []
}

function syncDict(key: string) {
  const obj: Record<string, any> = {}
  for (const r of keyRows[key] ?? []) {
    if (r.k.trim()) obj[r.k.trim()] = r.v
  }
  writePath(props.model, key, obj)
}

function addKeyRow(key: string) {
  ;(keyRows[key] ??= []).push({ k: '', v: '' })
}

function removeKeyRow(key: string, i: number) {
  const rows = keyRows[key]
  if (rows) {
    rows.splice(i, 1)
    syncDict(key)
  }
}

function updateKeyRow(key: string, i: number, field: 'k' | 'v', v: string) {
  const rows = keyRows[key]
  if (rows && rows[i]) {
    rows[i][field] = v
    syncDict(key)
  }
}

onMounted(() => {
  for (const spec of props.schema) {
    if (spec.kind === 'keyval') {
      keyRows[spec.key] = rowsFromDict(spec.key)
    }
  }
  loadJoinSources()
  document.addEventListener('focusin', onDocumentFocusIn)
})

onUnmounted(() => {
  document.removeEventListener('focusin', onDocumentFocusIn)
})
</script>

<style scoped>
.studio-form {
  display: flex;
  flex-direction: column;
  gap: 22px;
}
.form-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.form-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.form-hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0;
}
.form-empty {
  font-size: 12px;
  color: var(--text-tertiary);
  margin: 0;
  font-style: italic;
}
.input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: 14px;
  font-family: inherit;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 12%, transparent);
}
.input.mono {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 13px;
  resize: vertical;
}
.list-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.list-row.folder-row {
  flex-direction: column;
  align-items: stretch;
}
.folder-row > .input,
.folder-row-bottom .input,
.btn.folder-pick {
  height: 38px;
}
.folder-row-bottom {
  display: flex;
  gap: 8px;
  align-items: stretch;
}
.folder-row-bottom .input {
  flex: 1;
}
.btn.folder-pick {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  flex-shrink: 0;
  align-self: stretch;
  white-space: nowrap;
  padding: 0 12px;
  font-size: 14px;
}
.join-field {
  width: 100%;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 12px;
  color: var(--text-primary);
}
.chip-x {
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  font-size: 13px;
  line-height: 1;
  padding: 0;
}
.chip-x:hover {
  color: var(--text-primary);
}
.chip-input {
  flex: 1;
  min-width: 140px;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 12px;
}
.btn {
  align-self: flex-start;
  padding: 6px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}
.btn:hover {
  background: var(--bg-secondary);
  border-color: var(--text-tertiary);
}
.btn.sm {
  padding: 4px 10px;
  font-size: 12px;
}
.row-x {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  align-self: center;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--status-error);
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  font-family: inherit;
  transition: background 0.15s, color 0.15s;
}
.row-x:hover {
  background: color-mix(in srgb, var(--status-error) 10%, transparent);
  color: var(--status-error);
}
</style>
