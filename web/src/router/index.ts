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
  ],
})

export default router
