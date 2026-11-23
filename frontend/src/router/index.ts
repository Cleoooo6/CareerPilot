import { createRouter, createWebHistory } from 'vue-router'

import ChatPage from '@/pages/ChatPage.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/chat' },
    {
      path: '/chat',
      name: 'chat',
      component: ChatPage,
      meta: { title: 'AI 职业顾问' },
    },
    { path: '/:pathMatch(.*)*', redirect: '/chat' },
  ],
})