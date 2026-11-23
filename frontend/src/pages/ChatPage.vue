<script setup lang="ts">
import { onMounted } from 'vue'

import AppIcon from '@/components/AppIcon.vue'
import ErrorNotice from '@/components/ErrorNotice.vue'
import MessageInput from '@/components/MessageInput.vue'
import MessageList from '@/components/MessageList.vue'
import { useChatStore } from '@/stores/chat'

const chat = useChatStore()

const prompts = [
  {
    title: '梳理职业方向',
    detail: '不知道适合什么，从经历和目标聊起',
    text: '我还不确定适合什么方向，能帮我一起梳理吗？',
  },
  {
    title: '看清能力差距',
    detail: '目标岗位需要什么，我还缺什么',
    text: '帮我看看目标岗位需要哪些能力，我目前还缺什么。',
  },
  {
    title: '拆解下一步',
    detail: '把目标变成可以开始的行动',
    text: '帮我把下一步目标拆成可以执行的行动。',
  },
  {
    title: '了解市场趋势',
    detail: '看看目标方向的技能需求',
    text: '帮我看看目标方向最近的技能需求趋势。',
  },
]

function startPrompt(text: string) {
  if (!chat.isBusy()) void chat.send(text)
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

        <h2>探索职业方向，找到下一步</h2>
        <p class="page-lede">
          从你的经历和目标出发，一起梳理方向、判断差距、制定行动。
        </p>
      </div>
      <span class="quiet-note">对话会参考你确认的画像与市场数据</span>
    </header>

    <div class="chat-workspace">
      <div class="chat-stream">
        <div v-if="chat.messages.length === 0" class="chat-empty">
          <div class="chat-empty-mark">
            <AppIcon name="chat" :size="26" />
          </div>
          <h3>今天想从哪里开始</h3>
          <p>可以聊方向、看能力，也可以从一段经历说起。</p>
          <div class="prompt-grid">
            <button
              v-for="prompt in prompts"
              :key="prompt.title"
              type="button"
              class="prompt-card"
              :disabled="chat.isBusy()"
              @click="startPrompt(prompt.text)"
            >
              <strong>{{ prompt.title }}</strong>
              <span>{{ prompt.detail }}</span>
            </button>
          </div>
          <p class="chat-empty-note">
            重要画像更新会由你确认，对话不会自动修改。
          </p>
        </div>
        <MessageList
          v-else
          :messages="chat.messages"
          :streaming="chat.status === 'streaming'"
        />
      </div>

      <ErrorNotice
        v-if="chat.error"
        :error="chat.error"
        @dismiss="chat.clearError"
      />

      <MessageInput
        :streaming="chat.status === 'streaming' || chat.status === 'sending'"
        @send="chat.send"
        @stop="chat.stop"
      />
    </div>
  </section>
</template>