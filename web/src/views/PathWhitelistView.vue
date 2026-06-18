<template>
  <div class="whitelist-view">
    <!-- ── 列表模式 ── -->
    <template v-if="mode === 'list'">
      <div class="header">
        <h2>路径白名单</h2>
        <button class="btn btn-primary" @click="startAdd">添加</button>
      </div>

      <div v-if="loading" class="loading">加载中...</div>
      <div v-else-if="entries.length === 0" class="empty">尚未添加任何路径。</div>
      <div v-else class="entry-list">
        <div v-for="(entry, i) in entries" :key="i" class="entry-card">
          <div class="entry-body">
            <div class="entry-path">{{ entry.path }}</div>
            <div v-if="entry.description" class="entry-desc">{{ entry.description }}</div>
          </div>
          <div class="entry-actions">
            <button class="btn" @click="startEdit(i)">编辑</button>
            <button class="btn btn-danger" @click="confirmDelete(i)">删除</button>
          </div>
        </div>
      </div>
    </template>

    <!-- ── 表单模式 ── -->
    <template v-else>
      <div class="header">
        <h2>{{ editingIndex >= 0 ? '编辑' : '添加' }}路径</h2>
      </div>
      <div class="form-card">
        <div class="form-section">
          <label class="form-label">路径</label>
          <div class="path-row">
            <input
              v-model="formPath"
              class="input mono"
              placeholder="C:\path\to\directory"
              readonly
            />
            <button class="btn" @click="pickDir">选择目录</button>
          </div>
        </div>
        <div class="form-section">
          <label class="form-label">描述（可选）</label>
          <input
            v-model="formDesc"
            class="input"
            placeholder="用途说明"
          />
        </div>
        <div v-if="formError" class="msg error">{{ formError }}</div>
        <div class="form-actions">
          <button class="btn" @click="cancelForm">取消</button>
          <button class="btn btn-primary" :disabled="saving || !formPath.trim()" @click="handleSave">
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { api } from '@/api'
import type { WhitelistEntry } from '@/types'
import { ref, onMounted } from 'vue'

const mode = ref<'list' | 'form'>('list')
const entries = ref<WhitelistEntry[]>([])
const loading = ref(true)
const saving = ref(false)
const formError = ref('')
const editingIndex = ref(-1)
const formPath = ref('')
const formDesc = ref('')

async function loadEntries() {
  loading.value = true
  try {
    const res = await api.listWhitelist()
    entries.value = res.entries
  } catch (e: any) {
    console.error('加载白名单失败', e)
  } finally {
    loading.value = false
  }
}

async function pickDir() {
  try {
    const res = await api.selectFolder()
    if (res.path) {
      formPath.value = res.path
      formError.value = ''
    }
  } catch {
    formError.value = '选择目录失败'
  }
}

function startAdd() {
  editingIndex.value = -1
  formPath.value = ''
  formDesc.value = ''
  formError.value = ''
  mode.value = 'form'
}

function startEdit(i: number) {
  editingIndex.value = i
  formPath.value = entries.value[i].path
  formDesc.value = entries.value[i].description || ''
  formError.value = ''
  mode.value = 'form'
}

function cancelForm() {
  mode.value = 'list'
}

async function handleSave() {
  if (!formPath.value.trim()) return
  saving.value = true
  formError.value = ''
  try {
    const entry = { path: formPath.value.trim(), description: formDesc.value.trim() }
    if (editingIndex.value >= 0) {
      await api.updateWhitelistEntry(editingIndex.value, entry)
    } else {
      await api.addWhitelistEntry(entry)
    }
    await loadEntries()
    mode.value = 'list'
  } catch (e: any) {
    formError.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}

async function confirmDelete(i: number) {
  if (!window.confirm(`确定删除此路径？\n${entries.value[i].path}`)) return
  try {
    await api.deleteWhitelistEntry(i)
    entries.value.splice(i, 1)
  } catch (e: any) {
    console.error('删除失败', e)
  }
}

onMounted(loadEntries)
</script>

<style scoped>
.whitelist-view {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}
.header h2 {
  font-size: 20px;
  font-weight: 700;
}
.loading,
.empty {
  text-align: center;
  color: var(--text-secondary);
  padding: 40px 0;
}
.entry-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.entry-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--bg-card);
  transition: box-shadow 0.15s;
}
.entry-card:hover {
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.entry-body {
  flex: 1;
  min-width: 0;
}
.entry-path {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 13px;
  color: var(--text-primary);
  word-break: break-all;
  line-height: 1.4;
}
.entry-desc {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 2px;
}
.entry-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

/* ── 表单 ── */
.form-card {
  max-width: 560px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.form-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.form-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.path-row {
  display: flex;
  gap: 8px;
}
.path-row .input {
  flex: 1;
}
.input {
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 14px;
  color: var(--text-primary);
  background: var(--bg-card);
  outline: none;
  transition: border-color 0.15s;
}
.input:focus {
  border-color: var(--accent);
}
.input.mono {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 13px;
}
.form-actions {
  display: flex;
  gap: 8px;
}
.msg {
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
}
.msg.error {
  background: #fee2e2;
  color: #991b1b;
}

/* ── 按钮 ── */
.btn {
  padding: 6px 14px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-card);
  color: var(--text-primary);
  cursor: pointer;
  font-size: 13px;
  white-space: nowrap;
  transition: opacity 0.15s;
}
.btn:hover { opacity: 0.8; }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-primary {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
}
.btn-danger {
  color: var(--status-error);
  border-color: var(--status-error);
}
</style>
