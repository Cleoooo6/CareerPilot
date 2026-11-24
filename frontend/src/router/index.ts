import { createRouter, createWebHistory } from 'vue-router'

import ChatPage from '@/pages/ChatPage.vue'
import DashboardPage from '@/pages/DashboardPage.vue'
import MarketPage from '@/pages/MarketPage.vue'
import ProfilePage from '@/pages/ProfilePage.vue'
import RoadmapPage from '@/pages/RoadmapPage.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: DashboardPage,
      meta: { title: 'Dashboard' },
    },
    {
      path: '/chat',
      name: 'chat',
      component: ChatPage,
      meta: { title: 'AI Career Advisor' },
    },
    {
      path: '/profile',
      name: 'profile',
      component: ProfilePage,
      meta: { title: 'Profile' },
    },
    {
      path: '/market',
      name: 'market',
      component: MarketPage,
      meta: { title: 'Market Radar' },
    },
    {
      path: '/roadmap',
      name: 'roadmap',
      component: RoadmapPage,
      meta: { title: 'My Roadmap' },
    },
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
  ],
})