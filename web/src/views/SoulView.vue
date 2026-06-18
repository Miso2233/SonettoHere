<template>
  <div class="soul-view">
    <div class="header">
      <h2>人设 <span class="subtitle">SOUL</span></h2>
      <span v-if="saved" class="saved-indicator">已保存</span>
      <span v-else-if="saving" class="saving-indicator">保存中...</span>
    </div>
    <div v-if="loading" class="loading">加载中...</div>
    <textarea
      v-else
      v-model="content"
      class="persona-editor"
      :disabled="saving"
      placeholder="编辑人设内容..."
    ></textarea>
  </div>
</template>

<script setup lang="ts">
import { api } from '@/api'
import { ref, watch, onMounted } from 'vue'

const content = ref('')
const loading = ref(true)
const saving = ref(false)
const saved = ref(false)

let saveTimer: ReturnType<typeof setTimeout> | null = null

async function loadContent() {
  loading.value = true
  try {
    const res = await api.getPersona('soul')
    content.value = res.content
  } catch (e: any) {
    console.error('加载人设失败', e)
  } finally {
    loading.value = false
  }
}

async function saveContent() {
  saving.value = true
  try {
    await api.updatePersona('soul', content.value)
    saved.value = true
    setTimeout(() => { saved.value = false }, 2000)
  } catch (e: any) {
    console.error('保存人设失败', e)
  } finally {
    saving.value = false
  }
}

function debouncedSave() {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(saveContent, 800)
}

watch(content, () => {
  if (!loading.value) debouncedSave()
})

onMounted(loadContent)
</script>

<style scoped>
.soul-view {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
}
.header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
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
.saved-indicator {
  font-size: 12px;
  color: var(--status-ok);
}
.saving-indicator {
  font-size: 12px;
  color: var(--text-tertiary);
}
.loading {
  color: var(--text-secondary);
  padding: 40px 0;
  text-align: center;
}
.persona-editor {
  flex: 1;
  width: 100%;
  min-height: 300px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-primary);
  color: var(--text-primary);
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 14px;
  line-height: 1.6;
  resize: vertical;
  outline: none;
  transition: border-color 0.15s;
}
.persona-editor:focus {
  border-color: var(--accent);
}
.persona-editor:disabled {
  opacity: 0.6;
}
</style>
