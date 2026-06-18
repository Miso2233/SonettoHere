import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '@/views/ChatView.vue'
import MemoryView from '@/views/MemoryView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'chat', component: ChatView },
    { path: '/memory', name: 'memory', component: MemoryView },
    {
      path: '/playground',
      name: 'news',
      component: () => import('@/views/NewsView.vue'),
    },
    {
      path: '/providers',
      name: 'providers',
      component: () => import('@/views/ProvidersView.vue'),
    },
    {
      path: '/soul',
      name: 'soul',
      component: () => import('@/views/SoulView.vue'),
    },
    {
      path: '/user',
      name: 'user',
      component: () => import('@/views/UserView.vue'),
    },
    {
      path: '/path-whitelist',
      name: 'path-whitelist',
      component: () => import('@/views/PathWhitelistView.vue'),
    },
    {
      path: '/sonetto-blocker',
      name: 'sonetto-blocker',
      component: () => import('@/views/SonettoBlockerView.vue'),
    },
  ],
})

export default router
