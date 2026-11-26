import { createRouter, createWebHistory } from 'vue-router'

import ChatPage from '@/pages/ChatPage.vue'
import DashboardPage from '@/pages/DashboardPage.vue'
import LoginPage from '@/pages/LoginPage.vue'
import MarketPage from '@/pages/MarketPage.vue'
import ProfilePage from '@/pages/ProfilePage.vue'
import RegisterPage from '@/pages/RegisterPage.vue'
import RoadmapPage from '@/pages/RoadmapPage.vue'
import { authStore } from '@/stores/auth'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginPage,
      meta: { title: 'Sign in', public: true, layout: 'auth' },
    },
    {
      path: '/register',
      name: 'register',
      component: RegisterPage,
      meta: { title: 'Create account', public: true, layout: 'auth' },
    },
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

router.beforeEach(async (to) => {
  if (to.meta.public) return true
  await authStore.bootstrap()
  if (authStore.status === 'authenticated') return true
  return { name: 'login', query: { redirect: to.fullPath } }
})