<template>
  <div class="app-layout">
    <aside class="sidebar">
      <div class="sidebar-header">
        <h1 class="logo">SonettoHere</h1>
      </div>
      <nav class="sidebar-nav">
        <router-link to="/" class="nav-item">对话</router-link>
        <router-link to="/memory" class="nav-item">记忆</router-link>
      </nav>
      <SessionSidebar
        :sessions="sessions"
        :active-id="sessionId"
        @create="createSession"
        @switch="switchSession"
        @delete="deleteSession"
      />
    </aside>
    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useSession } from '@/composables/useSession'
import SessionSidebar from '@/components/SessionSidebar.vue'

const { sessionId, sessions, createSession, switchSession, deleteSession } =
  useSession()
</script>

<style>
*,
*::before,
*::after {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  --bg-primary: #faf8f5;
  --bg-secondary: #f3efe8;
  --bg-card: #ffffff;
  --text-primary: #3d342b;
  --text-secondary: #8b7e6e;
  --accent: #b8956a;
  --accent-light: #dcc7a8;
  --border: #e5ddd2;
  --user-bubble: #e8dccf;
  --shadow: 0 1px 3px rgba(61, 52, 43, 0.06);
  --radius: 10px;
}

html, body {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  font-size: 15px;
  color: var(--text-primary);
  background: var(--bg-primary);
}

#app {
  height: 100%;
}

.app-layout {
  display: flex;
  height: 100%;
}

.sidebar {
  width: 200px;
  min-width: 200px;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 20px 16px;
  gap: 24px;
}

.logo {
  font-size: 18px;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: -0.3px;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-item {
  display: block;
  padding: 8px 12px;
  border-radius: var(--radius);
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  transition: background 0.15s, color 0.15s;
}

.nav-item:hover {
  background: var(--bg-card);
  color: var(--text-primary);
}

.nav-item.router-link-active {
  background: var(--bg-card);
  color: var(--accent);
  font-weight: 600;
}

.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
</style>
