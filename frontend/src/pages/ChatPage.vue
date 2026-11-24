<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import ErrorNotice from '@/components/ErrorNotice.vue'
import MessageInput from '@/components/MessageInput.vue'
import MessageList from '@/components/MessageList.vue'
import { useChatStore } from '@/stores/chat'

const chat = useChatStore()
const inputRef = ref<InstanceType<typeof MessageInput> | null>(null)

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
})
</script>

<template>
  <section class="page chat-page">
    <header class="page-head chat-page-head">
      <div class="page-head-copy">
        <h2>AI Career Advisor <span class="page-title-cn">AI 职业顾问</span></h2>
        <p class="page-lede">
          聊聊你的方向、差距和下一步。它会引用你的画像，不确定的地方会说明。
        </p>
      </div>
      <div class="page-head-actions chat-head-actions">
        <span class="tag" :class="modeClass">{{ modeLabel }}</span>
      </div>
    </header>

    <div class="chat-workspace">
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
            <h3>今天想从哪里开始</h3>
            <p>可以聊方向、看能力，也可以从一段经历说起。</p>
            <div class="prompt-strip">
              <button
                v-for="prompt in prompts"
                :key="prompt.title"
                type="button"
                class="prompt-chip"
                :disabled="busy"
                @click="fillPrompt(prompt.text)"
              >
                {{ prompt.title }}
              </button>
            </div>
            <p class="chat-empty-note">
              重要画像更新会由你确认，对话不会自动修改。
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