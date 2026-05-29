<template>
  <div class="providers-view">
    <!-- ── 标题栏 ── -->
    <div class="header">
      <h2>提供商管理</h2>
      <button v-if="mode === 'list'" class="btn primary" @click="startAdd">+ 添加提供商</button>
      <button v-else class="btn" @click="cancelForm">← 返回列表</button>
    </div>

    <!-- ── 列表模式 ── -->
    <template v-if="mode === 'list'">
      <div v-if="loading" class="loading">加载中...</div>
      <div v-else-if="providers.length === 0" class="empty">
        尚未配置任何提供商。点击上方按钮添加。
      </div>
      <div v-else class="card-grid">
        <div v-for="p in providers" :key="p.id" class="provider-card">
          <div class="card-header">
            <strong>{{ p.label }}</strong>
            <span class="badge" :class="p.enabled ? 'on' : 'off'">
              {{ p.enabled ? '启用' : '停用' }}
            </span>
          </div>
          <div class="card-meta">
            <div class="meta-row"><span class="meta-label">类型</span>{{ p.provider_type }}</div>
            <div class="meta-row"><span class="meta-label">端点</span><span class="url">{{ p.base_url }}</span></div>
            <div class="meta-row"><span class="meta-label">模型</span>{{ p.models.length }} 个</div>
          </div>
          <div class="card-actions">
            <button class="btn sm" @click="testProvider(p.id)">测试</button>
            <button class="btn sm" @click="discoverProvider(p.id)">拉取模型</button>
            <button class="btn sm" @click="startEdit(p)">编辑</button>
            <button class="btn sm danger" @click="deleteProvider(p.id)">删除</button>
          </div>
          <div v-if="testResult?.[p.id]" class="test-result" :class="testResult[p.id].status">
            {{ testResult[p.id].status === 'ok' ? '✓' : '✗' }}
            {{ testResult[p.id].latency_ms }}ms —
            {{ testResult[p.id].detail || (testResult[p.id].status === 'ok' ? '连接正常' : '未知错误') }}
          </div>
        </div>
      </div>
    </template>

    <!-- ── 表单模式（添加/编辑） ── -->
    <form v-else class="wizard-form" @submit.prevent="handleSave">
      <div class="form-section">
        <label class="form-label">提供商</label>
        <select v-model="form.provider_type" class="input" :disabled="isEditing">
          <option v-for="preset in presets" :key="preset.id" :value="preset.id">
            {{ preset.label }}
          </option>
        </select>
      </div>

      <div class="form-section">
        <label class="form-label">显示名称</label>
        <input v-model="form.label" class="input" placeholder="例如: DeepSeek" />
      </div>

      <div class="form-section">
        <label class="form-label">API Key</label>
        <input v-model="form.api_key" class="input mono" type="password" :placeholder="isEditing ? '留空则不修改' : 'sk-...'" />
      </div>

      <div class="form-section">
        <label class="form-label">Base URL</label>
        <input v-model="form.base_url" class="input mono" placeholder="https://api.deepseek.com" />
      </div>

      <!-- 测试 & 拉取模型 -->
      <div class="form-row">
        <button type="button" class="btn" :disabled="!form.api_key || !form.base_url" @click="handleTest">
          {{ testing ? '测试中...' : '测试连接' }}
        </button>
        <button type="button" class="btn" :disabled="!form.api_key || !form.base_url" @click="handleDiscover">
          {{ discovering ? '拉取中...' : '拉取模型列表' }}
        </button>
      </div>
      <div v-if="formError" class="msg error">{{ formError }}</div>
      <div v-if="testOk" class="msg ok">连接成功 ({{ testLatency }}ms)</div>

      <!-- 模型列表 -->
      <div v-if="discoveredModels.length > 0" class="form-section">
        <label class="form-label">选择模型（{{ selectedModels.length }}/{{ discoveredModels.length }}）</label>
        <div class="model-list">
          <label v-for="m in discoveredModels" :key="m" class="model-item">
            <input type="checkbox" :value="m" :checked="selectedModels.includes(m)" @change="toggleModel(m)" />
            {{ m }}
          </label>
        </div>
        <button type="button" class="btn sm" @click="selectAllModels">全选</button>
        <button type="button" class="btn sm" @click="selectedModels = []">取消全选</button>
      </div>

      <div class="form-actions">
        <button type="submit" class="btn primary" :disabled="saving">
          {{ saving ? '保存中...' : (isEditing ? '更新' : '保存') }}
        </button>
        <button type="button" class="btn" @click="cancelForm">取消</button>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { api } from '@/api'
import type { ProviderConfig, TestConnectionResponse } from '@/types'
import { onMounted, ref, computed } from 'vue'

// ── 预设提供商列表 ──
const presets = [
  { id: 'deepseek', label: 'DeepSeek', base_url: 'https://api.deepseek.com' },
  { id: 'qwen', label: '通义千问 Qwen', base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  { id: 'kimi', label: '月之暗面 Kimi', base_url: 'https://api.moonshot.cn/v1' },
  { id: 'minimax', label: 'MiniMax', base_url: 'https://api.minimax.chat/v1' },
  { id: 'openrouter', label: 'OpenRouter', base_url: 'https://openrouter.ai/api/v1' },
  { id: 'custom', label: '自定义 Custom', base_url: '' },
]

// ── 模式 ──
const mode = ref<'list' | 'add' | 'edit'>('list')
const providers = ref<ProviderConfig[]>([])
const loading = ref(false)

// ── 表单 ──
const form = ref({ id: '', provider_type: 'deepseek', label: '', api_key: '', base_url: '' })
const isEditing = computed(() => mode.value === 'edit')
const editingId = ref('')

function presetBaseUrl(id: string) {
  return presets.find(p => p.id === id)?.base_url || ''
}

// 切换 preset 时自动填充 base_url
function onPresetChange(newType: string) {
  if (!isEditing.value) {
    form.value.base_url = presetBaseUrl(newType)
  }
}
// watch provider_type
import { watch } from 'vue'
watch(() => form.value.provider_type, onPresetChange)

// ── 测试连接 ──
const testing = ref(false)
const testOk = ref(false)
const testLatency = ref(0)
const formError = ref('')

async function handleTest() {
  testing.value = true
  formError.value = ''
  testOk.value = false
  try {
    const res = await api.testConnection({
      api_key: form.value.api_key,
      base_url: form.value.base_url,
    })
    if (res.status === 'ok') {
      testOk.value = true
      testLatency.value = res.latency_ms || 0
    } else {
      formError.value = res.detail || '连接失败'
    }
  } catch (e: any) {
    formError.value = e.message
  } finally {
    testing.value = false
  }
}

// ── 拉取模型 ──
const discovering = ref(false)
const discoveredModels = ref<string[]>([])
const selectedModels = ref<string[]>([])

async function handleDiscover() {
  discovering.value = true
  formError.value = ''
  try {
    const res = await api.discoverModels({
      api_key: form.value.api_key,
      base_url: form.value.base_url,
    })
    discoveredModels.value = res.models
    selectedModels.value = [...res.models]
  } catch (e: any) {
    formError.value = e.message
  } finally {
    discovering.value = false
  }
}

function toggleModel(m: string) {
  const idx = selectedModels.value.indexOf(m)
  if (idx >= 0) selectedModels.value.splice(idx, 1)
  else selectedModels.value.push(m)
}

function selectAllModels() {
  selectedModels.value = [...discoveredModels.value]
}

// ── CRUD ──
const saving = ref(false)
const testResult = ref<Record<string, TestConnectionResponse>>({})

async function loadProviders() {
  loading.value = true
  try {
    const res = await api.listProviders()
    providers.value = res.providers
  } catch (e: any) {
    console.error('Failed to load providers', e)
  } finally {
    loading.value = false
  }
}

function startAdd() {
  mode.value = 'add'
  form.value = { id: '', provider_type: 'deepseek', label: '', api_key: '', base_url: presetBaseUrl('deepseek') }
  discoveredModels.value = []
  selectedModels.value = []
  formError.value = ''
  testOk.value = false
}

function startEdit(p: ProviderConfig) {
  mode.value = 'edit'
  editingId.value = p.id
  form.value = {
    id: p.id,
    provider_type: p.provider_type,
    label: p.label,
    api_key: '',
    base_url: p.base_url,
  }
  discoveredModels.value = [...p.models]
  selectedModels.value = [...p.models]
  formError.value = ''
  testOk.value = false
}

function cancelForm() {
  mode.value = 'list'
  loadProviders()
}

async function handleSave() {
  saving.value = true
  formError.value = ''
  try {
    const body: any = {
      id: form.value.id || form.value.label.toLowerCase().replace(/\s+/g, '-'),
      provider_type: 'openai',
      label: form.value.label,
      api_key: form.value.api_key,
      base_url: form.value.base_url,
      models: selectedModels.value,
      enabled: true,
    }
    if (isEditing.value) {
      // PUT — only send changed fields
      const updateBody: any = { label: body.label, base_url: body.base_url, models: body.models }
      if (form.value.api_key) updateBody.api_key = form.value.api_key
      await api.updateProvider(editingId.value, updateBody)
    } else {
      await api.createProvider(body)
    }
    mode.value = 'list'
    await loadProviders()
  } catch (e: any) {
    formError.value = e.message
  } finally {
    saving.value = false
  }
}

async function deleteProvider(id: string) {
  if (!confirm(`确定删除提供商「${id}」？`)) return
  try {
    await api.deleteProvider(id)
    await loadProviders()
  } catch (e: any) {
    alert('删除失败: ' + e.message)
  }
}

async function testProvider(id: string) {
  try {
    const res = await api.testExistingProvider(id)
    testResult.value[id] = res
  } catch (e: any) {
    testResult.value[id] = { status: 'error', latency_ms: null, detail: e.message }
  }
}

async function discoverProvider(id: string) {
  try {
    await api.discoverModelsForExisting(id)
    await loadProviders()
  } catch (e: any) {
    alert('拉取失败: ' + e.message)
  }
}

onMounted(loadProviders)
</script>

<style scoped>
.providers-view {
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
.btn.sm { padding: 4px 10px; font-size: 12px; }
.btn.danger { color: var(--status-error); border-color: var(--status-error); }

/* ── List ── */
.loading, .empty {
  text-align: center;
  color: var(--text-secondary);
  padding: 40px 0;
}

.card-grid {
  display: grid;
  gap: 16px;
}

.provider-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.card-header strong {
  font-size: 15px;
}

.badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 600;
}
.badge.on { background: #d1fae5; color: #065f46; }
.badge.off { background: #f3f4f6; color: #6b7280; }

.card-meta {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 10px;
}
.meta-row {
  margin: 4px 0;
  display: flex;
  gap: 8px;
}
.meta-label {
  color: var(--text-primary);
  font-weight: 500;
  min-width: 40px;
}
.url {
  word-break: break-all;
}

.card-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.test-result {
  margin-top: 8px;
  font-size: 12px;
  padding: 6px 10px;
  border-radius: 6px;
}
.test-result.ok { background: #d1fae5; color: #065f46; }
.test-result.error { background: #fee2e2; color: #991b1b; }

/* ── Form ── */
.wizard-form {
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
.input:focus { border-color: var(--accent); }
.input.mono { font-family: 'SF Mono', 'Consolas', monospace; font-size: 13px; }
select.input { cursor: pointer; }

.form-row {
  display: flex;
  gap: 8px;
}

.msg {
  font-size: 13px;
  padding: 8px 12px;
  border-radius: 6px;
}
.msg.ok { background: #d1fae5; color: #065f46; }
.msg.error { background: #fee2e2; color: #991b1b; }

.model-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 240px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px;
}
.model-item {
  font-size: 13px;
  font-family: 'SF Mono', 'Consolas', monospace;
  padding: 4px 6px;
  cursor: pointer;
  border-radius: 4px;
}
.model-item:hover { background: var(--bg-secondary); }
.model-item input { margin-right: 8px; }

.form-actions {
  display: flex;
  gap: 8px;
  padding-top: 8px;
}
</style>
