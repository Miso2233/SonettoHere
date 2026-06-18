<template>
  <div class="blocker-view">
    <!-- ── 列表 ── -->
    <template v-if="!showForm">
      <div class="header">
        <h2>拒止锚 <span class="subtitle">SonettoBlocker</span></h2>
        <button class="btn btn-primary" @click="startAdd">添加</button>
      </div>

      <div v-if="loading" class="loading">加载中...</div>
      <div v-else-if="entries.length === 0" class="empty">
        <p>尚未添加任何拒止锚。</p>
        <p class="empty-hint">拒止锚会在所选目录中创建 <code>SonettoBlocker</code> 标记文件，<br>阻止任何文件工具访问该目录及其子目录。</p>
      </div>
      <div v-else class="entry-list">
        <div v-for="(entry, i) in entries" :key="i" class="entry-card">
          <div class="entry-body">
            <div class="entry-path">{{ entry.path }}</div>
            <div v-if="entry.description" class="entry-desc">{{ entry.description }}</div>
          </div>
          <button class="btn btn-danger" @click="confirmDelete(i)">删除</button>
        </div>
      </div>
    </template>

    <!-- ── 添加表单 ── -->
    <template v-else>
      <div class="header">
        <h2>添加拒止锚</h2>
      </div>
      <div class="form-card">
        <div class="form-section">
          <label class="form-label">目录</label>
          <div class="path-row">
            <input
              v-model="formPath"
              class="input mono"
              placeholder="选择或输入目录路径"
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
            {{ saving ? '创建中...' : '创建拒止锚' }}
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { api } from '@/api'
import type { BlockerEntry } from '@/types'
import { ref, onMounted } from 'vue'

const showForm = ref(false)
const entries = ref<BlockerEntry[]>([])
const loading = ref(true)
const saving = ref(false)
const formError = ref('')
const formPath = ref('')
const formDesc = ref('')

async function loadEntries() {
  loading.value = true
  try {
    const res = await api.listBlockers()
    entries.value = res.entries
  } catch (e: any) {
    console.error('加载拒止锚失败', e)
  } finally {
    loading.value = false
  }
}

function startAdd() {
  formPath.value = ''
  formDesc.value = ''
  formError.value = ''
  showForm.value = true
}

function cancelForm() {
  showForm.value = false
}

async function pickDir() {
  try {
    const res = await api.selectFolder()
    if (res.path) {
      formPath.value = res.path
      formError.value = ''
    }
  } catch (e: any) {
    formError.value = '选择目录失败'
  }
}

async function handleSave() {
  if (!formPath.value.trim()) return
  saving.value = true
  formError.value = ''
  try {
    await api.addBlocker({ path: formPath.value.trim(), description: formDesc.value.trim() })
    await loadEntries()
    showForm.value = false
  } catch (e: any) {
    formError.value = e.message || '创建失败'
  } finally {
    saving.value = false
  }
}

async function confirmDelete(i: number) {
  if (!window.confirm(`确定解除对此目录的拒止？\n${entries.value[i].path}\n\nSonettoBlocker 标记文件将被删除。`)) return
  try {
    await api.deleteBlocker(i)
    entries.value.splice(i, 1)
  } catch (e: any) {
    console.error('删除失败', e)
  }
}

onMounted(loadEntries)
</script>

<style scoped>
.blocker-view {
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
.subtitle {
  font-weight: 400;
  font-size: 14px;
  color: var(--text-tertiary);
  margin-left: 4px;
}
.loading,
.empty {
  text-align: center;
  color: var(--text-secondary);
  padding: 40px 0;
}
.empty-hint {
  font-size: 13px;
  margin-top: 8px;
  line-height: 1.6;
  color: var(--text-tertiary);
}
.empty-hint code {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  background: var(--bg-secondary);
  padding: 1px 5px;
  border-radius: 4px;
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
  transition: opacity 0.15s;
  white-space: nowrap;
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
