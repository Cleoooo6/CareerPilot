<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { ApiError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const email = ref('')
const displayName = ref('')
const password = ref('')
const confirmPassword = ref('')
const error = ref('')
const submitting = ref(false)

function validate(): string {
  if (!email.value.trim()) return '请输入邮箱'
  if (password.value.length < 10) return '密码至少需要 10 位'
  if (!/[A-Za-z]/.test(password.value) || !/\d/.test(password.value)) {
    return '密码必须同时包含字母和数字'
  }
  if (password.value !== confirmPassword.value) return '两次输入的密码不一致'
  return ''
}

function messageOf(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.code === 'CONFLICT') return '该邮箱已注册，请直接登录'
    if (err.code === 'WEAK_PASSWORD' || err.code === 'INVALID_EMAIL') return err.message
    return err.message
  }
  return '注册失败，请稍后重试'
}

async function submit(): Promise<void> {
  if (submitting.value) return
  error.value = validate()
  if (error.value) return
  submitting.value = true
  try {
    await auth.register(
      email.value.trim(),
      password.value,
      displayName.value.trim() || undefined,
    )
    await router.replace('/dashboard')
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
      <h1>从一个空白<br />工作区开始</h1>
      <p class="auth-lede">
        新账号拥有完全独立的职业画像、对话、简历与路线，不会继承任何示例数据。
      </p>
      <dl class="auth-facts">
        <div>
          <dt>独立</dt>
          <dd>数据按账号隔离</dd>
        </div>
        <div>
          <dt>可控</dt>
          <dd>随时导出或删除</dd>
        </div>
        <div>
          <dt>安全</dt>
          <dd>服务端会话认证</dd>
        </div>
      </dl>
    </section>

    <section class="auth-panel">
      <div class="auth-card">
        <header>
          <p class="auth-eyebrow">Create account</p>
          <h2>创建你的账号</h2>
          <p class="quiet-note">注册后将自动登录，并进入空白工作区。</p>
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
            <span>昵称（可选）</span>
            <input
              v-model="displayName"
              type="text"
              name="display_name"
              autocomplete="nickname"
              maxlength="80"
              placeholder="如何称呼你"
            />
          </label>
          <label class="field">
            <span>密码</span>
            <input
              v-model="password"
              type="password"
              name="password"
              autocomplete="new-password"
              required
              placeholder="至少 10 位，包含字母和数字"
            />
          </label>
          <label class="field">
            <span>确认密码</span>
            <input
              v-model="confirmPassword"
              type="password"
              name="confirm_password"
              autocomplete="new-password"
              required
              placeholder="再次输入密码"
            />
          </label>

          <p v-if="error" class="auth-error" role="alert">{{ error }}</p>

          <button class="button primary auth-submit" type="submit" :disabled="submitting">
            {{ submitting ? '创建中…' : '创建账号' }}
          </button>
        </form>

        <p class="auth-switch">
          已有账号？
          <RouterLink :to="{ name: 'login' }">返回登录</RouterLink>
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
  width: min(440px, 100%);
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