<template>
  <div class="message-row" :class="role">
    <div class="bubble" :class="role">
      <div class="bubble-text">{{ content }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ role: 'user' | 'assistant'; content: string }>()
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
  white-space: pre-wrap;
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
