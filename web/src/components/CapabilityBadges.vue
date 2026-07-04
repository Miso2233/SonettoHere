<template>
  <span class="cap-badges">
    <span v-if="caps?.vision === true" class="cap-icon" title="支持视觉">🖼️</span>
    <span v-else-if="caps?.vision === false" class="cap-icon unsupported" title="不支持视觉">🖼️✗</span>
    <span v-if="caps?.tool_call === true" class="cap-icon" title="支持工具调用">⚙️</span>
    <span v-else-if="caps?.tool_call === false" class="cap-icon unsupported" title="不支持工具调用">⚙️✗</span>
    <span v-if="caps?.structured_output === true" class="cap-icon" title="支持结构化输出">📋</span>
    <span v-else-if="caps?.structured_output === false" class="cap-icon unsupported" title="不支持结构化输出">📋✗</span>
  </span>
</template>

<script setup lang="ts">
defineProps<{
  capabilities: Record<string, boolean> | undefined
}>()
</script>

<style scoped>
.cap-badges {
  display: inline-flex;
  align-items: center;
  gap: 1px;
  margin-left: 2px;
  vertical-align: middle;
}
.cap-icon {
  font-size: 10px;
  line-height: 1;
}
.cap-icon.unsupported {
  opacity: 0.35;
}
</style>
