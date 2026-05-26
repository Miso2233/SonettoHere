<template>
  <div class="word-card protect-card">
    <div class="card-body">
      <span class="lock-icon">{{ isLocking ? '🔒' : '🔓' }}</span>
      <div>
        <div class="card-title">{{ isLocking ? '已添加密码保护' : '已解除密码保护' }}</div>
        <div class="card-filename" v-if="data.filename">📄 {{ data.filename }}</div>
        <div class="card-pw" v-if="data.password">密码已设置</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ data: Record<string, any> }>()

const isLocking = computed(() => props.data.action === 'protect')
</script>

<style scoped>
.word-card { padding: 12px 4px; }
.card-body {
  display: flex;
  align-items: center;
  gap: 12px;
}
.lock-icon { font-size: 26px; }
.card-title {
  font-size: 15px;
  font-weight: 600;
}
.protect-card .card-title { color: #b45309; }
.card-filename {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}
.card-pw {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
}
</style>
