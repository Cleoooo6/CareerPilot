<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

const route = useRoute()
const pageTitle = computed(() => String(route.meta.title ?? 'CareerPilot AI'))

const planned = [
  { label: 'Dashboard', hint: '发展驾驶舱', phase: '阶段八' },
  { label: 'Profile', hint: '个人职业画像', phase: '阶段三' },
  { label: 'Market', hint: '行业趋势', phase: '阶段四' },
  { label: 'Opportunities', hint: '职业机会', phase: '阶段七' },
  { label: 'Roadmap', hint: '成长规划', phase: '阶段七' },
]
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-mark">CP</span>
        <div>
          <div class="brand-name">CareerPilot</div>
          <div class="brand-sub">AI career copilot</div>
        </div>
      </div>

      <nav class="nav" aria-label="主导航">
        <div class="nav-section">当前可用</div>
        <RouterLink to="/chat" class="nav-item" active-class="active">
          <span class="nav-icon">C</span>
          <span>
            <strong>Chat</strong>
            <small>AI 职业顾问</small>
          </span>
        </RouterLink>

        <div class="nav-section">后续阶段</div>
        <div
          v-for="item in planned"
          :key="item.label"
          class="nav-item planned"
          aria-disabled="true"
        >
          <span class="nav-icon muted">·</span>
          <span>
            <strong>{{ item.label }}</strong>
            <small>{{ item.hint }} · {{ item.phase }}</small>
          </span>
        </div>
      </nav>

      <div class="sidebar-footer">
        <span class="dot"></span>
        Stage 01 · 工程初始化
      </div>
    </aside>

    <div class="app-body">
      <header class="topbar">
        <div>
          <div class="topbar-kicker">CareerPilot AI</div>
          <h1 class="topbar-title">{{ pageTitle }}</h1>
        </div>
        <div class="topbar-badges">
          <span class="badge">阶段一</span>
          <span class="badge mock">Mock 安全模式</span>
        </div>
      </header>

      <main class="app-main">
        <slot />
      </main>
    </div>
  </div>
</template>