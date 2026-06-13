<template>
  <HtmlSandbox v-if="useSandbox" :html="renderedHtml" />
  <div v-else class="markdown-body" v-html="renderedHtml"></div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { renderMarkdown, contentNeedsIsolation } from '@/utils/markdown'
import HtmlSandbox from './HtmlSandbox.vue'

const props = withDefaults(defineProps<{
  /** 原始 Markdown 文本 */
  content: string
  /** 强制使用 sandbox 渲染（即使检测不到 script 标签） */
  forceSandbox?: boolean
}>(), {
  forceSandbox: false,
})

const renderedHtml = computed(() => renderMarkdown(props.content))

const useSandbox = computed(() => {
  if (!props.content) return false
  if (props.forceSandbox) return true
  return contentNeedsIsolation(props.content)
})
</script>
