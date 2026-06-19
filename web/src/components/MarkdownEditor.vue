<template>
  <div class="md-editor-view">
    <div class="header">
      <h2>{{ title }} <span class="subtitle">{{ subtitle }}</span></h2>
      <span class="save-indicator" :class="saveState">
        {{ saveStateText }}
      </span>
      <span v-if="!saveState && content && content !== savedContent" class="save-hint">点击编辑区域外来保存</span>
    </div>
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else class="editor-wrapper">
      <Codemirror
        v-model="content"
        :extensions="extensions"
        :disabled="saving"
        :placeholder="placeholder"
        :style="{ height: '100%' }"
        :autofocus="false"
        :indent-with-tab="true"
        :tab-size="2"
        @blur="onBlur"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { Codemirror } from 'vue-codemirror'
import { markdown } from '@codemirror/lang-markdown'
import { EditorView } from '@codemirror/view'
import { api } from '@/api'

const props = defineProps<{
  type: 'soul' | 'user'
  title: string
  subtitle: string
  placeholder?: string
}>()

const content = ref('')
const savedContent = ref('')  // 记住上次保存的内容
const loading = ref(true)
const saving = ref(false)
const saveState = ref<'saved' | 'saving' | ''>('')

const extensions = [
  markdown(),
  EditorView.lineWrapping,
]

const saveStateText = computed(() => {
  if (saveState.value === 'saving') return '保存中...'
  if (saveState.value === 'saved') return '已保存'
  return ''
})

async function loadContent() {
  loading.value = true
  try {
    const res = await api.getPersona(props.type)
    content.value = res.content
    savedContent.value = res.content
  } catch (e: any) {
    console.error(`加载 ${props.type} 失败`, e)
  } finally {
    loading.value = false
  }
}

async function saveContent() {
  saving.value = true
  saveState.value = 'saving'
  try {
    await api.updatePersona(props.type, content.value)
    savedContent.value = content.value
    saveState.value = 'saved'
    setTimeout(() => { saveState.value = '' }, 2000)
  } catch (e: any) {
    console.error(`保存 ${props.type} 失败`, e)
  } finally {
    saving.value = false
  }
}

function onBlur() {
  if (content.value !== savedContent.value) {
    saveContent()
  }
}

onMounted(loadContent)
</script>

<style scoped>
.md-editor-view {
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
  flex-shrink: 0;
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

.save-indicator {
  font-size: 12px;
  transition: opacity 0.3s;
}
.save-indicator.saving {
  color: var(--text-tertiary);
}
.save-indicator.saved {
  color: var(--status-ok);
}

.save-hint {
  font-size: 12px;
  color: var(--text-tertiary);
  opacity: 0.8;
}

.loading {
  color: var(--text-secondary);
  padding: 40px 0;
  text-align: center;
}

.editor-wrapper {
  flex: 1;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  background: var(--bg-primary);
}

.editor-wrapper :deep(.cm-editor) {
  height: 100%;
}

.editor-wrapper :deep(.cm-scroller) {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  font-size: 15px;
  line-height: 1.6;
}

.editor-wrapper :deep(.cm-gutters) {
  background: var(--bg-primary);
  border-right: 1px solid var(--border);
}

.editor-wrapper :deep(.cm-gutterElement) {
  color: var(--text-tertiary);
}

.editor-wrapper :deep(.cm-content) {
  padding: 16px;
}

.editor-wrapper :deep(.cm-placeholder) {
  color: var(--text-tertiary);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  font-size: 15px;
}
</style>
