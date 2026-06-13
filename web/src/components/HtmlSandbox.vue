<template>
  <div class="html-sandbox-container" ref="container">
    <div v-if="!iframeLoaded" class="sandbox-loading">
      <span class="sandbox-spinner"></span>
      <!-- iframe 加载中 -->
    </div>
    <iframe
      ref="iframeRef"
      :srcdoc="iframeContent"
      sandbox="allow-scripts allow-modals"
      :style="{
        width: '100%',
        height: iframeHeight + 'px',
        border: 'none',
        display: 'block',
        overflow: 'hidden',
        visibility: iframeLoaded ? 'visible' : 'hidden',
        position: iframeLoaded ? 'relative' : 'absolute',
      }"
      title="sandboxed-content"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'

const props = withDefaults(defineProps<{
  html: string
}>(), {})

const container = ref<HTMLElement | null>(null)
const iframeRef = ref<HTMLIFrameElement | null>(null)
const iframeHeight = ref(200)
const iframeLoaded = ref(false)

/** 从当前文档根元素提取 CSS 自定义属性，传给 iframe 以保持主题一致 */
function getThemeCssVars(): string[] {
  const style = getComputedStyle(document.documentElement)
  const names = [
    '--bg-primary', '--bg-secondary', '--bg-card',
    '--text-primary', '--text-secondary', '--text-tertiary',
    '--accent', '--accent-light', '--border',
    '--user-bubble',
    '--status-ok', '--status-error', '--status-warn',
    '--shadow', '--radius',
  ]
  return names.map(n => `${n}: ${style.getPropertyValue(n).trim()};`)
}

/** 构建 iframe 内完整 HTML 文档 */
const iframeContent = computed(() => {
  const vars = getThemeCssVars()
  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  :root {
    ${vars.join('\n    ')}
  }
  *,
  *::before,
  *::after {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }
  html {
    height: 100%;
  }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
      'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
    font-size: 16px;
    line-height: 1.6;
    color: var(--text-primary, #1f2937);
    background: transparent;
    padding: 0;
    min-height: 40px;
    word-break: break-word;
    overflow-x: hidden;
  }

  /* ── Markdown 样式 ── */
  h1, h2, h3, h4, h5, h6 {
    margin: 16px 0 8px;
    font-weight: 600;
    line-height: 1.3;
  }
  h1 { font-size: 1.5em; }
  h2 { font-size: 1.3em; }
  h3 { font-size: 1.15em; }
  h4 { font-size: 1em; }
  h5 { font-size: 0.9em; }
  h6 { font-size: 0.85em; color: var(--text-secondary); }

  p { margin: 8px 0; }
  ul, ol { padding-left: 20px; margin: 8px 0; }
  li { margin: 4px 0; }

  code {
    background: var(--bg-primary);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.9em;
    font-family: 'SF Mono', 'Consolas', monospace;
  }
  pre {
    background: var(--bg-primary);
    padding: 12px;
    border-radius: 8px;
    overflow-x: auto;
    margin: 8px 0;
  }
  pre code {
    background: none;
    padding: 0;
    border-radius: 0;
    font-size: 13px;
  }

  blockquote {
    border-left: 3px solid var(--accent);
    padding: 4px 12px;
    margin: 8px 0;
    color: var(--text-secondary);
  }

  table {
    border-collapse: collapse;
    margin: 8px 0;
    width: 100%;
  }
  th, td {
    border: 1px solid var(--border);
    padding: 6px 12px;
    text-align: left;
  }
  th {
    background: var(--bg-secondary);
    font-weight: 600;
  }

  a {
    color: var(--accent);
    text-decoration: underline;
  }
  a:hover { opacity: 0.8; }

  strong { font-weight: 600; }

  hr {
    border: none;
    border-top: 1px solid var(--border);
    margin: 16px 0;
  }

  img {
    max-width: 100%;
    border-radius: 8px;
    height: auto;
  }

  input[type="checkbox"] {
    margin-right: 6px;
    accent-color: var(--accent);
  }

  /* 响应式媒体 */
  video, canvas, svg {
    max-width: 100%;
    height: auto;
  }

  /* 内联代码和图片等留边距 */
  .markdown-body > *:first-child { margin-top: 0; }
  .markdown-body > *:last-child  { margin-bottom: 0; }
</style>
</head>
<body>
<div class="markdown-body">
${props.html}
</div>
<script>
(function() {
  'use strict';
  function reportHeight() {
    var h = Math.max(
      document.body.scrollHeight,
      document.body.offsetHeight,
      document.documentElement.scrollHeight,
      document.documentElement.offsetHeight
    );
    if (h < 40) h = 40;
    parent.postMessage({ type: 'sandbox-resize', height: h }, '*');
  }
  if (document.readyState === 'complete') {
    reportHeight();
  } else {
    window.addEventListener('load', reportHeight);
  }
  if (window.ResizeObserver) {
    var ro = new ResizeObserver(reportHeight);
    ro.observe(document.body);
    ro.observe(document.documentElement);
  }
  // 兜底：动态内容可能延迟变化
  var delays = [100, 300, 800, 2000];
  delays.forEach(function(d) { setTimeout(reportHeight, d); });
})();
<\/script>
</body>
</html>`
})

/** 窗口消息监听：处理 iframe 高度上报 */
function handleMessage(event: MessageEvent) {
  if (event.data?.type === 'sandbox-resize' && typeof event.data.height === 'number') {
    iframeHeight.value = event.data.height
  }
}

function onIframeLoad() {
  iframeLoaded.value = true
}

onMounted(() => {
  window.addEventListener('message', handleMessage)
})

onUnmounted(() => {
  window.removeEventListener('message', handleMessage)
})
</script>

<style scoped>
.html-sandbox-container {
  position: relative;
  width: 100%;
  min-height: 40px;
}

.sandbox-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 0;
  color: var(--text-secondary);
  font-size: 13px;
}

.sandbox-spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: sandbox-spin 0.8s linear infinite;
}

@keyframes sandbox-spin {
  to { transform: rotate(360deg); }
}
</style>
