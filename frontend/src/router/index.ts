import { createRouter, createWebHistory } from 'vue-router'

import ChatPage from '@/pages/ChatPage.vue'
import MarketPage from '@/pages/MarketPage.vue'
import ProfilePage from '@/pages/ProfilePage.vue'
import RoadmapPage from '@/pages/RoadmapPage.vue'

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
    {
      path: '/profile',
      name: 'profile',
      component: ProfilePage,
      meta: { title: '职业画像' },
    },
    {
      path: '/market',
      name: 'market',
      component: MarketPage,
      meta: { title: '市场洞察' },
    },
    {
      path: '/roadmap',
      name: 'roadmap',
      component: RoadmapPage,
      meta: { title: '成长路线' },
    },
    { path: '/:pathMatch(.*)*', redirect: '/chat' },
  ],
})