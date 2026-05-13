<template>
  <div class="message-row" :class="role">
    <div class="bubble" :class="role">
      <div class="markdown-body" v-html="rendered"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { renderMarkdown } from '@/utils/markdown'

const props = defineProps<{ role: 'user' | 'assistant'; content: string }>()

const rendered = computed(() => renderMarkdown(props.content))
</script>

<style scoped>
.message-row {
  display: flex;
  padding: 4px 0;
}
.message-row.user {
  justify-content: flex-end;
}
.message-row.assistant {
  justify-content: flex-start;
}
.bubble {
  max-width: 72%;
  padding: 10px 16px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}
.bubble.user {
  background: var(--user-bubble);
  color: var(--text-primary);
  border-bottom-right-radius: 4px;
}
.bubble.assistant {
  background: var(--bg-card);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-bottom-left-radius: 4px;
}
</style>
