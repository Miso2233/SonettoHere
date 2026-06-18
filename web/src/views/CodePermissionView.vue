<template>
  <div class="perm-view">
    <div class="header">
      <h2>代码执行权限</h2>
      <span class="subtitle">管理永久允许/拒绝的代码规则</span>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="permissions.length === 0" class="empty">
      暂无永久权限规则。在执行代码时选择"永久允许"或"永久拒绝"即可添加。
    </div>
    <div v-else class="entry-list">
      <div v-for="(perm, i) in permissions" :key="i" class="entry-card">
        <div class="entry-body">
          <div class="entry-action-tag" :class="perm.action === 'allow' ? 'tag-allow' : 'tag-deny'">
            {{ perm.action === 'allow' ? '允许' : '拒绝' }}
          </div>
          <div class="entry-hash" :title="perm.hash">SHA256: {{ perm.hash.slice(0, 16) }}...</div>
          <pre class="entry-preview">{{ perm.code_preview }}</pre>
          <div v-if="perm.description" class="entry-desc">{{ perm.description }}</div>
        </div>
        <button class="btn btn-danger" @click="confirmDelete(i)">删除</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api'
import type { CodePermissionEntry } from '@/types'

const loading = ref(true)
const permissions = ref<CodePermissionEntry[]>([])

async function load() {
  loading.value = true
  try {
    const res = await api.listCodePermissions()
    permissions.value = res.permissions
  } catch (e: any) {
    console.error('加载代码权限失败', e)
  } finally {
    loading.value = false
  }
}

async function confirmDelete(i: number) {
  const perm = permissions.value[i]
  if (!window.confirm(`确定删除此${perm.action === 'allow' ? '允许' : '拒绝'}规则？`)) return
  try {
    await api.deleteCodePermission(i)
    permissions.value.splice(i, 1)
  } catch (e: any) {
    console.error('删除失败', e)
  }
}

onMounted(load)
</script>

<style scoped>
.perm-view {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}
.header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 20px;
}
.header h2 {
  font-size: 20px;
  font-weight: 700;
}
.subtitle {
  font-size: 13px;
  color: var(--text-secondary);
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
  align-items: flex-start;
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
.entry-action-tag {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  margin-bottom: 6px;
}
.tag-allow {
  background: #dcfce7;
  color: #166534;
}
.tag-deny {
  background: #fee2e2;
  color: #991b1b;
}
.entry-hash {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 11px;
  color: var(--text-tertiary);
  margin-bottom: 4px;
}
.entry-preview {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  color: var(--text-primary);
  background: var(--bg-secondary);
  padding: 8px 10px;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 80px;
  overflow-y: auto;
  margin: 0;
}
.entry-desc {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 4px;
}
.btn {
  padding: 6px 14px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-card);
  color: var(--text-primary);
  cursor: pointer;
  font-size: 13px;
  white-space: nowrap;
  flex-shrink: 0;
  margin-top: 2px;
  transition: opacity 0.15s;
}
.btn:hover { opacity: 0.8; }
.btn-danger {
  color: var(--status-error);
  border-color: var(--status-error);
}
</style>
