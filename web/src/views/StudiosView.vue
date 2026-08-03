<template>
  <div class="studios-view">
    <!-- ── 标题栏 ── -->
    <div class="header">
      <h2>工作坊管理</h2>
      <button v-if="mode === 'list'" class="btn primary" @click="startAdd">+ 新建工作坊</button>
      <button v-else class="btn" @click="cancelForm">← 返回列表</button>
    </div>

    <!-- ── 列表模式 ── -->
    <template v-if="mode === 'list'">
      <div v-if="loading" class="loading">加载中...</div>
      <div v-else-if="listError" class="msg error">{{ listError }}</div>
      <div v-else-if="studios.length === 0" class="empty">
        尚未创建任何工作坊。点击上方按钮新建，保存后即可在对话顶栏选择注入。
      </div>
      <div v-else class="studio-list">
        <div v-for="s in studios" :key="s.name" class="studio-row">
          <div class="studio-main">
            <div class="studio-name">{{ s.name }}</div>
            <div class="studio-desc">{{ s.description || '（无简介）' }}</div>
            <div class="studio-file">{{ s.filename }}</div>
          </div>
          <div class="studio-actions">
            <button class="action-btn" @click="startEdit(s)">编辑</button>
            <button class="row-x" @click="deleteStudio(s)" title="删除工作坊">&times;</button>
          </div>
        </div>
      </div>
    </template>

    <!-- ── 表单模式（添加/编辑） ── -->
    <form v-else class="wizard-form" @submit.prevent="handleSave">
      <StudioForm :model="model" :schema="schema" />
      <div v-if="formError" class="msg error">{{ formError }}</div>
      <div class="form-actions">
        <button type="submit" class="btn primary" :disabled="saving">
          {{ saving ? '保存中...' : (mode === 'edit' ? '更新' : '保存') }}
        </button>
        <button type="button" class="btn" @click="cancelForm">取消</button>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { api } from '@/api'
import StudioForm from '@/components/StudioForm.vue'
import type { StudioDocument, StudioFieldSpec, StudioInfo } from '@/types'
import { onMounted, reactive, ref } from 'vue'

const mode = ref<'list' | 'add' | 'edit'>('list')
const studios = ref<StudioInfo[]>([])
const loading = ref(false)
const saving = ref(false)
const listError = ref('')
const formError = ref('')

const model = reactive<StudioDocument>({})
const schema = ref<StudioFieldSpec[]>([])
let schemaLoaded = false
const editingName = ref('')

async function ensureSchema() {
  if (schemaLoaded) return
  const res = await api.getStudioSchema()
  schema.value = res.fields
  schemaLoaded = true
}

async function loadStudios() {
  loading.value = true
  listError.value = ''
  try {
    const res = await api.listStudios()
    studios.value = res.studios
  } catch (e: any) {
    listError.value = '加载失败: ' + e.message
  } finally {
    loading.value = false
  }
}

function resetModel(doc: StudioDocument) {
  for (const k of Object.keys(model)) delete model[k]
  Object.assign(model, doc)
}

async function startAdd() {
  formError.value = ''
  try {
    await ensureSchema()
  } catch (e: any) {
    formError.value = '无法加载工作坊表单结构: ' + e.message
    return
  }
  resetModel({})
  editingName.value = ''
  mode.value = 'add'
}

async function startEdit(s: StudioInfo) {
  formError.value = ''
  try {
    await ensureSchema()
    const doc = await api.getStudio(s.name)
    resetModel(doc)
    editingName.value = s.name
    mode.value = 'edit'
  } catch (e: any) {
    formError.value = '加载工作坊失败: ' + e.message
  }
}

function cancelForm() {
  mode.value = 'list'
  formError.value = ''
  loadStudios()
}

async function handleSave() {
  const name = String(model.name ?? '').trim()
  if (!name) {
    formError.value = '名称不能为空'
    return
  }
  saving.value = true
  formError.value = ''
  try {
    if (mode.value === 'add') {
      await api.createStudio(model)
    } else {
      await api.updateStudio(editingName.value, model)
    }
    mode.value = 'list'
    await loadStudios()
  } catch (e: any) {
    formError.value = e.message
  } finally {
    saving.value = false
  }
}

async function deleteStudio(s: StudioInfo) {
  if (!window.confirm(`确定删除工作坊「${s.name}」？`)) return
  try {
    await api.deleteStudio(s.name)
    await loadStudios()
  } catch (e: any) {
    alert('删除失败: ' + e.message)
  }
}

onMounted(loadStudios)
</script>

<style scoped>
.studios-view {
  flex: 1;
  overflow-y: auto;
  padding: 32px 24px 56px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.header {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  width: 100%;
  max-width: 720px;
  margin: 8px 0 28px;
  text-align: center;
}
.header h2 {
  font-size: 20px;
  font-weight: 700;
}

/* ── Buttons ── */
.btn {
  padding: 6px 14px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-card);
  color: var(--text-primary);
  cursor: pointer;
  font-size: 13px;
  transition: opacity 0.15s;
}
.btn:hover { opacity: 0.8; }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.btn.primary {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
}

/* ── List ── */
.loading, .empty {
  text-align: center;
  color: var(--text-secondary);
  padding: 40px 0;
  width: 100%;
  max-width: 720px;
}

.studio-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  width: 100%;
  max-width: 720px;
}

.studio-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: var(--shadow-sm);
}
.studio-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.studio-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}
.studio-desc {
  font-size: 13px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.studio-file {
  font-size: 11px;
  color: var(--text-tertiary);
  font-family: 'SF Mono', 'Consolas', monospace;
}
.studio-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
.action-btn {
  padding: 6px 14px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #ffffff;
  color: #6b7280;
  font-size: 12px;
  cursor: pointer;
  transition: opacity 0.15s;
}
.action-btn:hover { opacity: 0.7; }
.row-x {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--status-error);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  font-family: inherit;
  transition: background 0.15s;
}
.row-x:hover {
  background: color-mix(in srgb, var(--status-error) 10%, transparent);
}

/* ── Form ── */
.wizard-form {
  width: 100%;
  max-width: 640px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.form-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
}
.msg {
  font-size: 13px;
  padding: 8px 12px;
  border-radius: 6px;
  width: 100%;
  max-width: 720px;
}
.msg.error { background: #fee2e2; color: #991b1b; }
</style>
