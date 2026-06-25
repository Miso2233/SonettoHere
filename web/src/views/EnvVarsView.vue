<template>
  <div class="env-vars-view">
    <!-- ── 列表模式 ── -->
    <template v-if="mode === 'list'">
      <div class="header">
        <h2>工具环境变量</h2>
      </div>

      <details class="info-card">
        <summary class="info-summary">说明</summary>
        <div class="info-body">
          <p>此处管理工具运行所需的第三方服务 API Key 与凭据。值已做脱敏显示，修改后无需重启服务即可生效。</p>
        </div>
      </details>

      <div v-if="loading" class="loading">加载中...</div>
      <div v-else class="var-list">
        <div v-for="(item, i) in items" :key="item.key" class="var-card">
          <div class="var-body">
            <div class="var-label-row">
              <span class="var-label">{{ item.label }}</span>
              <span class="var-key">{{ item.key }}</span>
            </div>
            <div class="var-desc">{{ item.description }}</div>
            <div class="var-value-row">
              <span class="var-value" :class="{ unset: !item.is_set }">
                {{ item.is_set ? item.value : '未设置' }}
              </span>
              <button class="btn btn-sm" @click="startEdit(i)">{{ item.is_set ? '修改' : '设置' }}</button>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- ── 编辑模式 ── -->
    <template v-else>
      <div class="header">
        <h2>{{ itemForEdit?.is_set ? '修改' : '设置' }}{{ editingLabel }}</h2>
      </div>
      <div class="form-card">
        <div class="form-section">
          <label class="form-label">Key</label>
          <div class="input mono readonly">{{ itemForEdit?.key }}</div>
        </div>
        <div class="form-section">
          <label class="form-label">{{ itemForEdit?.is_set ? '新值' : '值' }}</label>
          <input
            ref="valueInputRef"
            v-model="formValue"
            class="input mono"
            type="password"
            :placeholder="`输入${itemForEdit?.label}的 API Key`"
            autocomplete="off"
            @keydown.enter.prevent="handleSave"
          />
        </div>
        <div v-if="itemForEdit?.is_set" class="form-section">
          <label class="form-label">当前值（脱敏）</label>
          <div class="input mono readonly">{{ itemForEdit.value }}</div>
        </div>
        <div v-if="formError" class="msg error">{{ formError }}</div>
        <div v-if="formSuccess" class="msg success">{{ formSuccess }}</div>
        <div class="form-actions">
          <button class="btn" @click="cancelForm">取消</button>
          <button class="btn btn-primary" :disabled="saving || !formValue.trim()" @click="handleSave">
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { api } from '@/api'
import type { EnvVarItem } from '@/types'
import { ref, computed, onMounted, nextTick } from 'vue'

const mode = ref<'list' | 'form'>('list')
const items = ref<EnvVarItem[]>([])
const loading = ref(true)
const saving = ref(false)
const formError = ref('')
const formSuccess = ref('')
const editingIndex = ref(-1)
const formValue = ref('')
const valueInputRef = ref<HTMLInputElement | null>(null)

const itemForEdit = computed(() => {
  if (editingIndex.value < 0) return null
  return items.value[editingIndex.value] ?? null
})

const editingLabel = computed(() => {
  return itemForEdit.value ? ` ${itemForEdit.value.label}` : ''
})

async function loadVars() {
  loading.value = true
  try {
    const res = await api.listEnvVars()
    items.value = res.env_vars
  } catch (e: any) {
    console.error('加载环境变量失败', e)
  } finally {
    loading.value = false
  }
}

function startEdit(i: number) {
  editingIndex.value = i
  formValue.value = ''
  formError.value = ''
  formSuccess.value = ''
  mode.value = 'form'
  nextTick(() => valueInputRef.value?.focus())
}

function cancelForm() {
  mode.value = 'list'
  formError.value = ''
  formSuccess.value = ''
}

async function handleSave() {
  const item = itemForEdit.value
  if (!item || !formValue.value.trim()) return
  saving.value = true
  formError.value = ''
  formSuccess.value = ''
  try {
    const res = await api.updateEnvVar(item.key, formValue.value.trim())
    formSuccess.value = `${item.label} 已更新`
    // 更新本地缓存
    item.value = res.masked_value
    item.is_set = true
    setTimeout(() => cancelForm(), 1200)
  } catch (e: any) {
    formError.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}

onMounted(loadVars)
</script>

<style scoped>
.env-vars-view {
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

.loading {
  text-align: center;
  color: var(--text-secondary);
  padding: 40px 0;
}

/* ── 信息卡片 ── */
.info-card {
  margin-bottom: 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--bg-card);
  overflow: hidden;
}

.info-summary {
  padding: 10px 16px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
}

.info-summary:hover {
  opacity: 0.8;
}

.info-body {
  padding: 0 16px 12px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);
}

/* ── 变量列表 ── */
.var-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.var-card {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--bg-card);
  transition: box-shadow 0.15s;
}

.var-card:hover {
  box-shadow: var(--shadow-sm);
}

.var-body {
  flex: 1;
  min-width: 0;
}

.var-label-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}

.var-label {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.var-key {
  font-size: 11px;
  color: var(--text-tertiary);
  font-family: 'SF Mono', 'Consolas', monospace;
}

.var-desc {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.var-value-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.var-value {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 13px;
  color: var(--text-primary);
  word-break: break-all;
}

.var-value.unset {
  color: var(--text-tertiary);
  font-style: italic;
}

/* ── 表单 ── */
.form-card {
  max-width: 520px;
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

.input.readonly {
  background: var(--bg-secondary);
  color: var(--text-secondary);
  cursor: default;
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

.msg.success {
  background: #dcfce7;
  color: #166534;
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

.btn-sm {
  padding: 4px 10px;
  font-size: 12px;
}
</style>
