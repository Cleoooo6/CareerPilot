<script setup lang="ts">
import { computed, onMounted } from 'vue'

import ErrorNotice from '@/components/ErrorNotice.vue'
import MessageInput from '@/components/MessageInput.vue'
import MessageList from '@/components/MessageList.vue'
import StatusTimeline from '@/components/StatusTimeline.vue'
import { useChatStore } from '@/stores/chat'

const chat = useChatStore()

const modeLabel = computed(() => {
  if (!chat.llmStatus) return '模型状态加载中'
  return chat.llmStatus.mode === 'mock'
    ? `Mock 安全模式 · ${chat.llmStatus.model}`
    : `真实模式 · ${chat.llmStatus.model}`
})

const conversationLabel = computed(() =>
  chat.conversationId ? chat.conversationId.slice(0, 8) : '待创建',
)

onMounted(() => {
  void chat.loadMeta()
  void chat.restore()
})
</script>

<template>
  <section class="chat-page">
    <header class="chat-head">
      <div class="chat-head-copy">
        <p class="eyebrow">CAREER CONTEXT / STAGE 01</p>
        <h2>把职业问题说清楚，再一起拆解。</h2>
        <p class="lede">
          当前只验证对话、SSE、Trace 与工程链路；不会伪造画像、市场或规划结论。
        </p>
      </div>
      <div class="mode-pill" :class="{ mock: chat.llmStatus?.mode === 'mock' }">
        <span class="mode-dot"></span>
        {{ modeLabel }}
      </div>
    </header>

    <div class="chat-surface">
      <div class="context-strip">
        <span>会话 {{ conversationLabel }}</span>
        <span>工具 {{ chat.tools?.registered.length ?? 0 }} 个（Mock）</span>
        <span>{{ chat.messages.length }} 条消息</span>
      </div>

      <div v-if="chat.messages.length === 0" class="welcome">
        <div class="welcome-grid">
          <article class="welcome-card accent">
            <span class="welcome-kicker">现在可用</span>
            <h3>最小 Agent 闭环</h3>
            <ul>
              <li>Single-Agent：START → INTENT → ECHO → END</li>
              <li>SSE 推送节点开始与完成事件</li>
              <li>PostgreSQL 持久化会话、消息、Run 与 Trace</li>
            </ul>
          </article>
          <article class="welcome-card">
            <span class="welcome-kicker">明确边界</span>
            <h3>不伪造业务能力</h3>
            <ul>
              <li>职业画像 / 行业市场 / 机会匹配尚未实现</li>
              <li>技能差距 / 成长规划尚未实现</li>
              <li>默认 Mock 模型，无真实 API 调用</li>
            </ul>
          </article>
          <article class="welcome-card">
            <span class="welcome-kicker">下一步</span>
            <h3>先验证工程底座</h3>
            <ul>
              <li>阶段二：通用基础设施与工具调用</li>
              <li>阶段三：用户体系与职业画像</li>
              <li>阶段四：就业市场数据采集与分析</li>
            </ul>
          </article>
        </div>
        <p class="welcome-note">
          可以先输入「你好」验证完整链路。输入「帮我看看技能画像」会得到明确的未实现说明，而不是伪造结果。
        </p>
      </div>

      <MessageList v-else :messages="chat.messages" />

      <StatusTimeline v-if="chat.timeline.length" :items="chat.timeline" />

      <ErrorNotice v-if="chat.error" :error="chat.error" @dismiss="chat.clearError" />

      <MessageInput
        :streaming="chat.status === 'streaming' || chat.status === 'sending'"
        @send="chat.send"
        @stop="chat.stop"
      />
    </div>
  </section>
</template>