<template>
  <BubbleChrome :tool-call="toolCall">
    <!-- ── 运行中 ── -->
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <WordIcon class="word-icon-pulse" />
      <span>{{ actionLabel }}</span>
      <span class="running-dots"></span>
    </div>

    <!-- ── 错误 ── -->
    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      <WordIcon />
      <div class="error-content">
        <div class="error-title">{{ actionLabel }} 失败</div>
        <div class="error-msg">{{ toolCall.output || '未知错误' }}</div>
      </div>
    </div>

    <!-- ── 完成 — 按 action 类别渲染不同卡片 ── -->
    <template v-else-if="toolCall.status === 'done'">
      <!-- 创建 / 复制 / 合并文档 -->
      <CreateCard v-if="isAction('create_document','copy_document','merge_documents')" :data="td" />

      <!-- 文档信息 -->
      <InfoCard v-else-if="isAction('get_document_info')" :data="td" />

      <!-- 文档大纲 / 文档列表 -->
      <OutlineCard v-else-if="isAction('get_document_outline','list_documents','get_document_xml','get_document_text')" :data="td" />

      <!-- 添加标题 / 添加段落 / 插入内容 -->
      <InsertCard v-else-if="isAction('add_heading','add_paragraph','add_picture','add_page_break','insert_heading','insert_paragraph','insert_list','add_toc')" :data="td" />

      <!-- 表格操作 -->
      <TableCard v-else-if="isAction('add_table') || td.action?.startsWith('table_')" :data="td" />

      <!-- 脚注 / 尾注 -->
      <FootnoteCard v-else-if="td.action?.includes('footnote') || td.action?.includes('endnote')" :data="td" />

      <!-- 查找替换 / 搜索文本 -->
      <SearchCard v-else-if="isAction('search_replace','find_text')" :data="td" />

      <!-- 格式化 / 样式 -->
      <FormatCard v-else-if="isAction('format_text','format_table','create_style')" :data="td" />

      <!-- 保护 / 密码 -->
      <ProtectCard v-else-if="isAction('protect','unprotect')" :data="td" />

      <!-- 转换 PDF -->
      <ConvertCard v-else-if="isAction('convert_to_pdf')" :data="td" />

      <!-- 评论 -->
      <CommentsCard v-else-if="td.action?.startsWith('get_comments')" :data="td" />

      <!-- 删除段落 / 替换区块 -->
      <EditCard v-else-if="isAction('delete_paragraph','replace_block','replace_anchors','get_paragraph')" :data="td" />

      <!-- 默认回退 -->
      <DefaultCard v-else :data="td" :raw-output="toolCall.output" />
    </template>
  </BubbleChrome>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ToolCall } from '@/types'
import BubbleChrome from './_shared/BubbleChrome.vue'
import WordIcon from './_shared/WordIcon.vue'

// ── 各分类卡片组件 ──
import CreateCard from './_word/CreateCard.vue'
import InfoCard from './_word/InfoCard.vue'
import OutlineCard from './_word/OutlineCard.vue'
import InsertCard from './_word/InsertCard.vue'
import TableCard from './_word/TableCard.vue'
import FootnoteCard from './_word/FootnoteCard.vue'
import SearchCard from './_word/SearchCard.vue'
import FormatCard from './_word/FormatCard.vue'
import ProtectCard from './_word/ProtectCard.vue'
import ConvertCard from './_word/ConvertCard.vue'
import CommentsCard from './_word/CommentsCard.vue'
import EditCard from './_word/EditCard.vue'
import DefaultCard from './_word/DefaultCard.vue'

const props = defineProps<{ toolCall: ToolCall }>()
defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

// ── 工具数据：优先取 toolData，其次从 output 解析 ──
const td = computed<Record<string, any>>(() => {
  if (props.toolCall.toolData) {
    return props.toolCall.toolData as Record<string, any>
  }
  // 无 toolData 时在气泡内尝试解析 output（兜底）
  if (props.toolCall.output) {
    try {
      const parsed = JSON.parse(props.toolCall.output)
      if (parsed?.data) return parsed.data as Record<string, any>
      return parsed
    } catch {
      // 纯文本，回退
    }
  }
  return {}
})

const shortName = computed(() => {
  return props.toolCall.name.replace(/^word_/, '')
})

function isAction(...actions: string[]): boolean {
  return actions.includes(td.value.action) || actions.includes(shortName.value)
}

const actionLabel = computed(() => {
  if (td.value.action && td.value.action !== shortName.value) {
    return td.value.action.replace(/_/g, ' ')
  }
  return shortName.value.replace(/_/g, ' ')
})
</script>

<style scoped>
.bubble-running {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.word-icon-pulse {
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

.running-dots::after {
  content: '...';
  animation: dots 1.2s steps(3, end) infinite;
}

@keyframes dots {
  0% { content: ''; }
  33% { content: '.'; }
  66% { content: '..'; }
  100% { content: '...'; }
}

.bubble-error {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 0;
}

.error-content {
  flex: 1;
}

.error-title {
  font-size: 14px;
  font-weight: 600;
  color: #b91c1c;
  margin-bottom: 4px;
}

.error-msg {
  font-size: 12px;
  color: #991b1b;
  line-height: 1.5;
  word-break: break-word;
}
</style>
