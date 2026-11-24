<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import AppIcon from '@/components/AppIcon.vue'

const route = useRoute()
const pageTitle = computed(() => String(route.meta.title ?? 'CareerPilot AI'))
const isChat = computed(() => route.name === 'chat')

const navItems = [
  {
    to: '/dashboard',
    icon: 'dashboard' as const,
    en: 'Dashboard',
    cn: '职业发展总览',
  },
  {
    to: '/chat',
    icon: 'chat' as const,
    en: 'AI Career Advisor',
    cn: 'AI 职业顾问',
  },
  {
    to: '/profile',
    icon: 'profile' as const,
    en: 'Profile',
    cn: '职业画像',
  },
  {
    to: '/market',
    icon: 'market' as const,
    en: 'Market Radar',
    cn: '市场洞察',
  },
  {
    to: '/roadmap',
    icon: 'roadmap' as const,
    en: 'My Roadmap',
    cn: '成长路线',
  },
]
</script>

<template>
  <div class="app-shell" :class="{ 'is-chat': isChat }">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-mark" aria-hidden="true">C</span>
        <span class="brand-copy">
          <span class="brand-name">CareerPilot AI</span>
          <span class="brand-sub">智绘职涯</span>
        </span>
      </div>

      <nav class="nav" aria-label="主导航">
        <div class="nav-label">Workspace</div>
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav-item"
          active-class="is-active"
        >
          <AppIcon :name="item.icon" :size="18" />
          <span class="nav-item-copy">
            <span class="nav-item-en">{{ item.en }}</span>
            <span class="nav-item-cn">{{ item.cn }}</span>
          </span>
        </RouterLink>
      </nav>

      <div class="sidebar-foot">
        <span>让职业选择有依据</span>
        <span>让个人成长有方向</span>
      </div>
    </aside>

    <div class="app-body">
      <header class="topbar">
        <div class="topbar-inner">
          <h1>{{ pageTitle }}</h1>
        </div>
      </header>
      <main class="app-main">
        <slot />
      </main>
    </div>
  </div>
</template>