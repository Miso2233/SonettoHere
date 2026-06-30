<template>
  <div class="image-thumbnail" :title="label" @click="handleClick">
    <img v-if="blobUrl" :src="blobUrl" :alt="label" loading="lazy" class="thumbnail-img" />
    <div v-else-if="loading" class="thumbnail-loading">
      <span class="loading-spinner"></span>
    </div>
    <div v-else class="thumbnail-error">
      <Icon name="file" :size="20" />
      <span class="thumbnail-error-text">加载失败</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { api } from '@/api'
import Icon from '@/components/Icon.vue'

const props = defineProps<{
  path: string
  label: string
}>()

const emit = defineEmits<{
  click: [path: string]
}>()

const blobUrl = ref<string | null>(null)
const loading = ref(true)

onMounted(async () => {
  try {
    blobUrl.value = await api.getImageBlobUrl(props.path)
  } catch {
    blobUrl.value = null
  } finally {
    loading.value = false
  }
})

onUnmounted(() => {
  if (blobUrl.value) {
    URL.revokeObjectURL(blobUrl.value)
  }
})

function handleClick() {
  emit('click', props.path)
}
</script>

<style scoped>
.image-thumbnail {
  width: 80px;
  height: 80px;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  flex-shrink: 0;
  border: 1px solid color-mix(in srgb, var(--text-primary) 10%, transparent);
  background: color-mix(in srgb, var(--text-primary) 4%, transparent);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: box-shadow 0.15s, transform 0.15s;
}
.image-thumbnail:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  transform: scale(1.05);
}

.thumbnail-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.thumbnail-loading {
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid color-mix(in srgb, var(--text-primary) 12%, transparent);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: thumb-spin 0.6s linear infinite;
}

@keyframes thumb-spin {
  to { transform: rotate(360deg); }
}

.thumbnail-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  color: var(--text-tertiary);
}

.thumbnail-error-text {
  font-size: 9px;
  line-height: 1;
}
</style>
