<template>
  <div class="message-row" :class="role">
    <div class="bubble" :class="role">
      <RenderMarkdown v-if="content" :content="content" />
      <div v-if="imageRefs?.length" class="image-thumbnails">
        <ImageThumbnail
          v-for="(img, idx) in imageRefs"
          :key="idx"
          :path="img.path"
          :label="img.label"
          @click="handleImageClick"
        />
      </div>
      <div v-if="refs?.length" class="ref-chips">
        <ReferenceChip
          v-for="(r, idx) in refs"
          :key="idx"
          :chip="r"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { FileRef, ParsedRef } from '@/utils/references';
import ImageThumbnail from './ImageThumbnail.vue';
import ReferenceChip from './ReferenceChip.vue';
import RenderMarkdown from './RenderMarkdown.vue';

const props = defineProps<{
  role: 'user' | 'assistant'
  content: string
  refs?: ParsedRef[]
  imageRefs?: FileRef[]
}>()

function handleImageClick(path: string) {
  // 预留：点击缩略图可放大预览
}
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
  border: 1px solid rgba(0, 0, 0, 0.2);
  border-bottom-right-radius: 4px;
}
.bubble.assistant {
  background: var(--bg-card);
  color: var(--text-primary);
  border-bottom-left-radius: 4px;
}
.image-thumbnails {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-start;
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px solid color-mix(in srgb, var(--text-primary) 12%, transparent);
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
