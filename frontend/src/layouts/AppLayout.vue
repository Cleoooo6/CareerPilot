<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import AppIcon from '@/components/AppIcon.vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const signingOut = ref(false)

const pageTitle = computed(() => String(route.meta.title ?? 'CareerPilot AI'))
const isChat = computed(() => route.name === 'chat')
const displayName = computed(
  () => auth.user?.display_name || auth.user?.email || '我的账户',
)
const initial = computed(() => displayName.value.slice(0, 1).toUpperCase())

async function handleLogout(): Promise<void> {
  if (signingOut.value) return
  signingOut.value = true
  try {
    await auth.logout()
    await router.replace({ name: 'login' })
  } finally {
    signingOut.value = false
  }
}

watch(
  () => route.fullPath,
  async () => {
    await nextTick()
    document.getElementById('main')?.focus({ preventScroll: true })
  },
)

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
    <a class="skip-link" href="#main">跳到主要内容</a>
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
          :aria-current="route.path === item.to ? 'page' : undefined"
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
          <span class="topbar-title">{{ pageTitle }}</span>
          <div class="topbar-account">
            <span class="topbar-avatar" aria-hidden="true">{{ initial }}</span>
            <span class="topbar-user">{{ displayName }}</span>
            <button
              class="topbar-logout"
              type="button"
              :disabled="signingOut"
              @click="handleLogout"
            >
              {{ signingOut ? '退出中…' : '退出' }}
            </button>
          </div>
        </div>
      </header>
      <main id="main" class="app-main" tabindex="-1">
        <slot />
      </main>
    </div>
  </div>
</template>
<style scoped>
.topbar-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  height: 100%;
}
.topbar-account {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: var(--text-sm);
  color: var(--muted);
}
.topbar-avatar {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--accent-soft);
  color: var(--accent-text);
  font-weight: 700;
  font-size: var(--text-xs);
}
.topbar-user {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.topbar-logout {
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  border-radius: var(--radius-pill);
  padding: 5px 12px;
  font-size: var(--text-xs);
  cursor: pointer;
}
.topbar-logout:hover {
  border-color: var(--border-strong);
}
.topbar-logout:disabled {
  color: var(--disabled);
  cursor: default;
}
</style>