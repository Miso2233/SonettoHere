import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import fs from 'node:fs'
import path from 'node:path'

function loadApiToken(): string {
  try {
    const yamlPath = path.resolve(__dirname, '..', 'api', 'data', 'auth_token.yaml')
    const raw = fs.readFileSync(yamlPath, 'utf-8')
    const match = raw.match(/^token:\s*(.+)$/m)
    const token = match?.[1]?.trim()
    if (token) return token
    console.warn('[vite] auth_token.yaml 中未找到 token')
    return ''
  } catch {
    console.warn('[vite] auth_token.yaml 读取失败，API 调用将因无 Token 而返回 401')
    return ''
  }
}

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  define: {
    __API_TOKEN__: JSON.stringify(loadApiToken()),
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
