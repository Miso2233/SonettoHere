<template>
  <div class="blocker-view">
    <!-- ── 列表 ── -->
    <template v-if="!showForm">
      <div class="header">
        <h2>拒止锚 <span class="subtitle">SonettoBlocker</span></h2>
        <button class="btn btn-primary" @click="startAdd">添加</button>
      </div>

      <details class="rule-card">
        <summary class="rule-summary">规则说明</summary>
        <div class="rule-body">
          <p>拒止锚是一种强制安全机制，优先级高于白名单：</p>
          <ul>
            <li>在指定目录中创建 <code>SonettoBlocker</code> 标记文件（无扩展名），AI 的所有文件工具将无法访问该目录及其所有子目录。</li>
            <li>检查时会从目标目录逐级向上查找，一旦发现任何父目录包含 <code>SonettoBlocker</code> 文件即强制阻断。</li>
            <li>访问被拒止锚阻断时，白名单中即使有对应的放行条目也不会生效。</li>
          </ul>
          <p class="rule-note">路径白名单及完整权限规则参见设置页的「<router-link to="/path-whitelist">路径白名单</router-link>」页面。</p>
        </div>
      </details>

      <div v-if="loading" class="loading">加载中...</div>
      <div v-else-if="entries.length === 0" class="empty">
        <p>尚未添加任何拒止锚。</p>
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
/* ── 规则说明 ── */
.rule-card {
  margin-bottom: 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--bg-card);
  overflow: hidden;
}
.rule-summary {
  padding: 10px 16px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
}
.rule-summary:hover {
  opacity: 0.8;
}
.rule-body {
  padding: 0 16px 12px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);
}
.rule-body ul {
  margin: 6px 0;
  padding-left: 20px;
}
.rule-body li {
  margin-bottom: 4px;
}
.rule-body code {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  background: var(--bg-secondary);
  padding: 1px 5px;
  border-radius: 3px;
}
.rule-note {
  margin-top: 8px;
  padding: 8px 10px;
  background: #f0f5ff;
  border-radius: 6px;
  color: #1a4a8a;
  font-size: 12px;
}
.rule-note code {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  background: #dbeafe;
  padding: 1px 5px;
  border-radius: 3px;
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
  box-shadow: var(--shadow-sm);
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
