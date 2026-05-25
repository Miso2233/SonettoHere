<template>
  <BubbleChrome :tool-call="toolCall">
    <!-- 运行中 -->
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>正在{{ actionLabel }}...</span>
    </div>

    <!-- 错误 -->
    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '操作失败' }}
    </div>

    <!-- 完成 -->
    <template v-else-if="toolCall.status === 'done'">
      <div class="word-result">
        <div class="word-icon-row">
          <svg class="word-icon" viewBox="0 0 24 24" fill="none" width="28" height="28">
            <rect x="3" y="2" width="18" height="20" rx="2" fill="#2b579a" />
            <path d="M7 12l2 4 2-4h1.5l-2.5 5h-2l-2.5-5H7zM12 12h5v1.5h-5V12zM12 15h4v1.5h-4V15z" fill="white" />
          </svg>
          <span class="word-action-label">{{ actionLabel }}</span>
        </div>
        <div class="word-filename" v-if="filename">📄 {{ filename }}</div>
        <div class="word-params" v-if="paramLines.length">
          <div class="param-row" v-for="(line, i) in paramLines" :key="i">
            <span class="param-key">{{ line.key }}:</span>
            <span class="param-val">{{ line.val }}</span>
          </div>
        </div>
        <div class="word-msg" v-if="shortOutput">{{ shortOutput }}</div>
        <div class="word-detail" v-else-if="toolCall.output && needDetail">
          <pre class="detail-code">{{ toolCall.output }}</pre>
        </div>
      </div>
    </template>
  </BubbleChrome>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ToolCall } from '@/types'
import BubbleChrome from './_shared/BubbleChrome.vue'

const props = defineProps<{ toolCall: ToolCall }>()
defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

// ── 工具名 → 中文动作映射 ──
const ACTION_LABELS: Record<string, string> = {
  create_document: '创建文档',
  copy_document: '复制文档',
  get_document_info: '查看文档信息',
  get_document_text: '提取文档文本',
  get_document_outline: '查看文档大纲',
  list_available_documents: '列出文档目录',
  get_document_xml: '查看文档底层 XML',
  insert_header_near_text: '插入标题',
  insert_line_or_paragraph_near_text: '插入段落',
  insert_numbered_list_near_text: '插入列表',
  add_paragraph: '添加段落',
  add_heading: '添加标题',
  add_picture: '插入图片',
  add_table: '添加表格',
  add_page_break: '插入分页符',
  delete_paragraph: '删除段落',
  search_and_replace: '查找替换',
  create_custom_style: '创建自定义样式',
  format_text: '格式化文本',
  format_table: '格式化表格',
  set_table_cell_shading: '设置单元格底色',
  apply_table_alternating_rows: '设置交替行颜色',
  highlight_table_header: '高亮表头',
  merge_table_cells: '合并单元格区域',
  merge_table_cells_horizontal: '水平合并单元格',
  merge_table_cells_vertical: '垂直合并单元格',
  set_table_cell_alignment: '设置单元格对齐',
  set_table_alignment_all: '设置表格对齐',
  set_table_column_width: '设置列宽',
  set_table_column_widths: '批量设置列宽',
  set_table_width: '设置表格宽度',
  auto_fit_table_columns: '自动调整列宽',
  format_table_cell_text: '格式化单元格文本',
  set_table_cell_padding: '设置单元格边距',
  protect_document: '添加密码保护',
  unprotect_document: '解除密码保护',
  add_footnote_to_document: '添加脚注',
  add_footnote_after_text: '在文本后添加脚注',
  add_footnote_before_text: '在文本前添加脚注',
  add_footnote_enhanced: '添加脚注（增强）',
  add_endnote_to_document: '添加尾注',
  customize_footnote_style: '自定义脚注样式',
  delete_footnote_from_document: '删除脚注',
  add_footnote_robust: '添加脚注（鲁棒）',
  delete_footnote_robust: '删除脚注（鲁棒）',
  validate_document_footnotes: '验证文档脚注',
  get_paragraph_text_from_document: '获取段落文本',
  find_text_in_document: '在文档中搜索',
  convert_to_pdf: '转换为 PDF',
  replace_paragraph_block_below_header: '替换标题下方段落',
  replace_block_between_manual_anchors: '替换锚点间内容',
  get_all_comments: '获取所有评论',
  get_comments_by_author: '按作者筛选评论',
  get_comments_for_paragraph: '获取段落评论',
}

// ── 从 toolCall.name 提取动作名（去掉 word_ 前缀）──
const shortName = computed(() => {
  return props.toolCall.name.replace(/^word_/, '')
})

const actionLabel = computed(() => {
  return ACTION_LABELS[shortName.value] || shortName.value.replace(/_/g, ' ')
})

// ── 解析 input JSON 提取关键参数 ──
const parsedInput = computed<Record<string, string>>(() => {
  try {
    return JSON.parse(props.toolCall.input) as Record<string, string>
  } catch {
    return {}
  }
})

const filename = computed(() => parsedInput.value.filename || parsedInput.value.source_filename || '')

// ── 关键参数白名单（显示次要参数） ──
const KEY_PARAMS = new Set([
  'filename', 'source_filename', 'destination_filename', 'output_filename',
  'directory', 'password',
])

const paramLines = computed(() => {
  const lines: { key: string; val: string }[] = []
  for (const [k, v] of Object.entries(parsedInput.value)) {
    if (v && !KEY_PARAMS.has(k) && String(v).length < 80) {
      const label = PARAM_LABELS[k] || k.replace(/_/g, ' ')
      lines.push({ key: label, val: String(v) })
    }
  }
  return lines.slice(0, 4)
})

const PARAM_LABELS: Record<string, string> = {
  text: '内容', paragraph_text: '内容', heading_text: '标题',
  search_text: '搜索', replace_text: '替换为',
  level: '级别', rows: '行数', columns: '列数',
  style_name: '样式', font_name: '字体', font_size: '字号',
  table_index: '表格', paragraph_index: '段落',
  image_path: '图片路径',
}

// ── 结果文本（取 output 摘要） ──
const shortOutput = computed(() => {
  if (!props.toolCall.output) return ''
  const s = props.toolCall.output
  if (s.length < 120) return s
  // 尝试从 output 中提取关键信息（如成功消息）
  const match = s.match(/"[^"]*(?:成功|完成|已|created|added|saved)[^"]*"/i)
  if (match) return match[0].replace(/"/g, '')
  if (s.includes('Error') || s.includes('error')) return s.slice(0, 120) + '...'
  return ''
})

const needDetail = computed(() => {
  return !shortOutput.value && !!props.toolCall.output
})
</script>

<style scoped>
.bubble-running {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.bubble-error {
  font-size: 13px;
  color: #b91c1c;
  padding: 4px 0;
}

/* ── 结果卡片 ── */
.word-result {
  padding: 12px 4px;
}

.word-icon-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.word-icon {
  flex-shrink: 0;
}

.word-action-label {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.word-filename {
  font-size: 13px;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  padding: 6px 10px;
  border-radius: 6px;
  margin-bottom: 8px;
  display: inline-block;
}

.word-params {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  margin-bottom: 6px;
}

.param-row {
  display: flex;
  gap: 4px;
  font-size: 12px;
}

.param-key {
  color: var(--text-secondary);
}

.param-val {
  color: var(--text-primary);
  font-weight: 500;
  word-break: break-all;
}

.word-msg {
  font-size: 13px;
  color: var(--text-primary);
  padding: 6px 0;
  line-height: 1.5;
}

.word-detail {
  margin-top: 8px;
}

.detail-code {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 11px;
  line-height: 1.5;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--bg-primary);
  padding: 8px 10px;
  border-radius: 6px;
  max-height: 160px;
  overflow-y: auto;
  margin: 0;
}
</style>
