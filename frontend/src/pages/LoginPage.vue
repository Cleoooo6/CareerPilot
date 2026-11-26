<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { ApiError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const email = ref('')
const password = ref('')
const error = ref('')
const submitting = ref(false)

const redirect = computed(() => {
  const target = route.query.redirect
  const value = Array.isArray(target) ? target[0] : target
  return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//')
    ? value
    : '/dashboard'
})

function messageOf(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.code === 'INVALID_CREDENTIALS') return '邮箱或密码不正确'
    if (err.code === 'TOO_MANY_ATTEMPTS') return '登录尝试过于频繁，请稍后再试'
    if (err.code === 'ACCOUNT_DISABLED') return '账号已被禁用'
    return err.message
  }
  return '登录失败，请稍后重试'
}

async function submit(): Promise<void> {
  if (submitting.value) return
  error.value = ''
  submitting.value = true
  try {
    await auth.login(email.value.trim(), password.value)
    await router.replace(redirect.value)
  } catch (err) {
    error.value = messageOf(err)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="auth-shell">
    <section class="auth-brand" aria-hidden="true">
      <span class="brand-mark lg">C</span>
      <p class="auth-kicker">CareerPilot AI</p>
      <h1>让职业选择<br />有依据</h1>
      <p class="auth-lede">
        用一份可信的职业画像，连接真实市场证据与可执行的成长路线。
      </p>
      <dl class="auth-facts">
        <div>
          <dt>画像</dt>
          <dd>事实与推断分离</dd>
        </div>
        <div>
          <dt>市场</dt>
          <dd>证据驱动洞察</dd>
        </div>
        <div>
          <dt>路线</dt>
          <dd>阶段化行动清单</dd>
        </div>
      </dl>
    </section>

    <section class="auth-panel">
      <div class="auth-card">
        <header>
          <p class="auth-eyebrow">Welcome back</p>
          <h2>登录 CareerPilot</h2>
          <p class="quiet-note">使用你的邮箱和密码继续。</p>
        </header>

        <form class="auth-form" novalidate @submit.prevent="submit">
          <label class="field">
            <span>邮箱</span>
            <input
              v-model="email"
              type="email"
              name="email"
              autocomplete="email"
              required
              placeholder="you@example.com"
            />
          </label>
          <label class="field">
            <span>密码</span>
            <input
              v-model="password"
              type="password"
              name="password"
              autocomplete="current-password"
              required
              placeholder="输入密码"
            />
          </label>

          <p v-if="error" class="auth-error" role="alert">{{ error }}</p>

          <button class="button primary auth-submit" type="submit" :disabled="submitting">
            {{ submitting ? '登录中…' : '登录' }}
          </button>
        </form>

        <p class="auth-switch">
          还没有账号？
          <RouterLink :to="{ name: 'register', query: route.query }">创建账号</RouterLink>
        </p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.auth-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
  background: var(--bg);
}
.auth-brand {
  background: var(--navy);
  color: #f4f7f9;
  padding: 64px clamp(32px, 6vw, 88px);
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 18px;
}
.brand-mark.lg {
  width: 52px;
  height: 52px;
  font-size: 24px;
}
.auth-kicker {
  margin: 8px 0 0;
  font-size: var(--text-sm);
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #9fb3c2;
}
.auth-brand h1 {
  margin: 0;
  font-size: clamp(34px, 4vw, 52px);
  line-height: 1.12;
  letter-spacing: -0.02em;
}
.auth-lede {
  margin: 0;
  max-width: 34ch;
  color: #c7d2da;
  font-size: var(--text-md);
  line-height: 1.7;
}
.auth-facts {
  margin: 18px 0 0;
  display: grid;
  gap: 14px;
  border-top: 1px solid rgba(255, 255, 255, 0.16);
  padding-top: 22px;
}
.auth-facts div {
  display: flex;
  gap: 14px;
  align-items: baseline;
}
.auth-facts dt {
  width: 44px;
  color: #8fa6b6;
  font-size: var(--text-xs);
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.auth-facts dd {
  margin: 0;
  font-size: var(--text-base);
}
.auth-panel {
  display: grid;
  place-items: center;
  padding: 48px 24px;
}
.auth-card {
  width: min(420px, 100%);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-popover);
  padding: 34px;
  display: grid;
  gap: 20px;
}
.auth-eyebrow {
  margin: 0 0 6px;
  font-size: var(--text-xs);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent-text);
}
.auth-card h2 {
  margin: 0;
  font-size: var(--text-xl);
  letter-spacing: -0.01em;
}
.auth-form {
  display: grid;
  gap: 14px;
}
.auth-error {
  margin: 0;
  color: var(--danger);
  font-size: var(--text-sm);
}
.auth-submit {
  width: 100%;
  margin-top: 4px;
}
.auth-switch {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--muted);
}
.auth-switch a {
  color: var(--accent-text);
  font-weight: 600;
}
@media (max-width: 900px) {
  .auth-shell {
    grid-template-columns: 1fr;
  }
  .auth-brand {
    display: none;
  }
}
</style>