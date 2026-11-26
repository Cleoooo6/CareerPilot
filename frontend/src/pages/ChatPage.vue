<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import ErrorNotice from '@/components/ErrorNotice.vue'
import MessageInput from '@/components/MessageInput.vue'
import MessageList from '@/components/MessageList.vue'
import { getMarketOverview } from '@/api/market'
import { getProfile } from '@/api/profile'
import { getCurrentRoadmap } from '@/api/roadmap'
import { useChatStore } from '@/stores/chat'
import type { MarketOverview } from '@/types/market'
import type { ProfileOut } from '@/types/profile'
import type { Roadmap } from '@/types/roadmap'
import { profileCompletion } from '@/utils/dashboardView'
import { flattenRoadmapTasks } from '@/utils/roadmapView'

const chat = useChatStore()
const inputRef = ref<InstanceType<typeof MessageInput> | null>(null)
const contextProfile = ref<ProfileOut | null>(null)
const contextMarket = ref<MarketOverview | null>(null)
const contextRoadmap = ref<Roadmap | null>(null)
const contextLoading = ref(true)
const contextError = ref(false)

const contextTargetRole = computed(
  () => contextProfile.value?.data.goals.target_role.trim() ?? '',
)
const contextTargetIndustry = computed(
  () => contextProfile.value?.data.goals.target_industry.trim() ?? '',
)
const contextCompletion = computed(() =>
  profileCompletion(contextProfile.value?.data ?? null),
)
const contextMarketSample = computed(
  () => contextMarket.value?.meta.sample_size ?? 0,
)
const contextMarketSynthetic = computed(
  () => contextMarket.value?.meta.dataset_kinds.includes('synthetic') ?? false,
)
const contextNextTask = computed(
  () =>
    flattenRoadmapTasks(contextRoadmap.value).find(
      (task) => task.status === 'in_progress',
    ) ??
    flattenRoadmapTasks(contextRoadmap.value).find(
      (task) => task.status === 'pending',
    ) ??
    null,
)

async function loadContext() {
  contextLoading.value = true
  contextError.value = false
  const [profile, market, roadmap] = await Promise.allSettled([
    getProfile(),
    getMarketOverview(),
    getCurrentRoadmap(),
  ])
  contextProfile.value =
    profile.status === 'fulfilled' ? profile.value.profile : null
  contextMarket.value =
    market.status === 'fulfilled' ? market.value : null
  contextRoadmap.value =
    roadmap.status === 'fulfilled' ? roadmap.value.roadmap : null
  contextError.value =
    profile.status === 'rejected' &&
    market.status === 'rejected' &&
    roadmap.status === 'rejected'
  contextLoading.value = false
}

const prompts = [
  {
    title: '梳理职业方向',
    text: '我还不确定适合什么方向，能帮我一起梳理吗？',
  },
  {
    title: '看清能力差距',
    text: '帮我看看目标岗位需要哪些能力，我目前还缺什么。',
  },
  {
    title: '拆解下一步',
    text: '帮我把下一步目标拆成可以执行的行动。',
  },
  {
    title: '了解市场趋势',
    text: '帮我看看目标方向最近的技能需求趋势。',
  },
]

const busy = computed(
  () => chat.status === 'sending' || chat.status === 'streaming',
)
const mode = computed(() => chat.llmStatus?.mode ?? '')
const modeLabel = computed(() =>
  mode.value === 'mock'
    ? '演示模式'
    : mode.value === 'real'
      ? '真实模型'
      : '模式读取中',
)
const modeClass = computed(() =>
  mode.value === 'mock'
    ? 'tag-inference'
    : mode.value === 'real'
      ? 'tag-evidence'
      : 'tag',
)
const modeNote = computed(() =>
  mode.value === 'mock'
    ? '演示模式：回复来自预置文本，不调用真实模型，也不生成 AI 推断/建议标签。'
    : mode.value === 'real'
      ? '真实模型：回答中的推断与建议会按输出类型标注。'
      : '模型模式读取中或读取失败；不会冒充真实模型响应。',
)
const composerHint = computed(() =>
  mode.value === 'mock'
    ? '演示模式 · 预置回复，不代表真实模型判断；不提供 AI 推断标签'
    : mode.value === 'real'
      ? '回答中的判断会标注「AI 推断 / AI 建议」；涉及画像时会注明来源'
      : '正在读取模型模式…',
)
const thinking = computed(
  () =>
    chat.status === 'sending' ||
    (chat.status === 'streaming' &&
      chat.messages[chat.messages.length - 1]?.role === 'user'),
)

function fillPrompt(text: string) {
  inputRef.value?.fill(text)
}

function retry() {
  if (chat.lastUserMessage) {
    void chat.send(chat.lastUserMessage)
  }
}

onMounted(() => {
  void chat.loadMeta()
  void chat.restore()
  void loadContext()
})
</script>

<template>
  <section class="page chat-page">
    <header class="page-head chat-page-head">
      <div class="page-head-copy">
        <h1>AI Career Advisor <span class="page-title-cn">AI 职业顾问</span></h1>
        <p class="page-lede">
          聊聊你的方向、差距和下一步。它会引用你的画像，不确定的地方会说明。
        </p>
      </div>
      <div class="page-head-actions chat-head-actions">
        <span class="tag" :class="modeClass">{{ modeLabel }}</span>
      </div>
    </header>

    <div class="chat-workspace">
      <div class="chat-main">
        <div class="chat-stream">
        <div
          v-if="chat.restoreState === 'loading' || chat.restoreState === 'idle'"
          class="skeleton-page"
          style="padding: 30px"
        >
          <div class="skeleton skeleton-line md"></div>
          <div class="skeleton skeleton-line sm"></div>
          <div class="skeleton skeleton-block" style="height: 120px"></div>
        </div>
        <div v-else-if="chat.restoreState === 'error'" class="state-card">
          <h3>历史消息加载失败</h3>
          <p>{{ chat.restoreError?.message || '请重试或开始新对话。' }}</p>
          <div class="page-head-actions">
            <button type="button" class="button primary" @click="chat.restore()">
              重试加载历史
            </button>
            <button
              type="button"
              class="button secondary"
              @click="chat.startNewConversation()"
            >
              开始新对话
            </button>
          </div>
        </div>
        <div v-else-if="chat.messages.length === 0" class="chat-empty">
          <div class="chat-empty-inner">
            <p class="section-label">Advisor briefing</p>
            <h3>今天想从哪里开始</h3>
            <p>
              可以聊方向、看能力，也可以从一段经历说起。回答会引用你的画像、市场统计与成长路线。
            </p>
            <div class="prompt-grid">
              <button
                v-for="prompt in prompts"
                :key="prompt.title"
                type="button"
                class="prompt-card"
                :disabled="busy"
                @click="fillPrompt(prompt.text)"
              >
                <strong>{{ prompt.title }}</strong>
                <span>{{ prompt.text }}</span>
              </button>
            </div>
            <p class="chat-empty-note">
              重要画像更新会由你确认，对话不会自动修改；演示模式不冒充真实模型判断。
            </p>
          </div>
        </div>
        <MessageList
          v-else
          :messages="chat.messages"
          :streaming="chat.status === 'streaming'"
          :thinking="thinking"
          :profile-used="chat.profileUsed"
        />
      </div>

        <aside class="chat-context" aria-label="对话上下文">
          <p class="section-label">Your context</p>
          <p v-if="contextLoading" class="state-loading" role="status">
            正在读取上下文…
          </p>
          <p v-else-if="contextError" class="note">
            上下文暂时无法读取；对话本身不受影响。
          </p>
          <template v-else>
            <div class="context-card">
              <strong>目标方向</strong>
              <p v-if="contextTargetRole || contextTargetIndustry">
                {{ contextTargetRole || '待设置岗位' }}
                <span v-if="contextTargetIndustry"> · {{ contextTargetIndustry }}</span>
              </p>
              <p v-else>待补充</p>
            </div>
            <div class="context-card">
              <strong>画像完整度</strong>
              <p>
                {{ contextCompletion }}%
                <span>按已确认资料</span>
              </p>
            </div>
            <div class="context-card">
              <strong>市场样本</strong>
              <p v-if="contextMarketSample">
                {{ contextMarketSample }} 条 ·
                {{ contextMarketSynthetic ? '演示数据' : '真实数据' }}
              </p>
              <p v-else>暂无样本</p>
              <RouterLink to="/market" class="link-button">
                去 Market Radar
              </RouterLink>
            </div>
            <div class="context-card">
              <strong>路线下一步</strong>
              <p v-if="contextNextTask">{{ contextNextTask.title }}</p>
              <p v-else>暂无待推进任务</p>
              <RouterLink to="/roadmap" class="link-button">
                查看 My Roadmap
              </RouterLink>
            </div>
          </template>
          <p class="context-note">只读引用；对话不会自动修改画像或路线。</p>
        </aside>
      </div>

      <ErrorNotice
        v-if="chat.error"
        :error="chat.error"
        retryable
        @dismiss="chat.clearError"
        @retry="retry"
      />

      <MessageInput
        ref="inputRef"
        :streaming="chat.status === 'streaming' || chat.status === 'sending'"
        :hint="composerHint"
        @send="chat.send"
        @stop="chat.stop"
      />
    </div>
  </section>
</template>