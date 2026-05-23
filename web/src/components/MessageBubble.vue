<template>
  <div class="message-row" :class="role">
    <div class="bubble" :class="role">
      <div v-if="parsed.cleanText" class="markdown-body" v-html="rendered"></div>
      <div v-if="parsed.refs.length" class="ref-chips">
        <ReferenceChip
          v-for="(ref, idx) in parsed.refs"
          :key="idx"
          :type="ref.type"
          :label="ref.label"
          :path="ref.path"
          :text="ref.text"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { renderMarkdown } from '@/utils/markdown';
import { parseReferences } from '@/utils/references';
import { computed } from 'vue';
import ReferenceChip from './ReferenceChip.vue';

const props = defineProps<{ role: 'user' | 'assistant'; content: string }>()

const parsed = computed(() => {
  if (props.role !== 'user') {
    return { cleanText: props.content, refs: [] }
  }
  return parseReferences(props.content)
})

const rendered = computed(() => renderMarkdown(parsed.value.cleanText))
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
  font-size: 16px;
  line-height: 1.6;
  word-break: break-word;
  box-shadow: var(--shadow);
}
.bubble.user {
  background: var(--user-bubble);
  color: var(--text-primary);
  border-bottom-right-radius: 4px;
}
.bubble.assistant {
  background: var(--bg-card);
  color: var(--text-primary);
  border-bottom-left-radius: 4px;
}
.ref-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px solid color-mix(in srgb, var(--text-primary) 12%, transparent);
}
</style>
