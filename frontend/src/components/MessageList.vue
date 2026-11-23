<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'

import type { ChatMessage } from '@/types/chat'
import { userFacingText } from '@/utils/userFacing'

const props = withDefaults(
  defineProps<{ messages: ChatMessage[]; streaming?: boolean }>(),
  { streaming: false },
)
const container = ref<HTMLElement | null>(null)
const stickToBottom = ref(true)

function formatTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function onScroll() {
  const element = container.value
  if (!element) return
  stickToBottom.value =
    element.scrollHeight - element.scrollTop - element.clientHeight < 80
}

async function scrollToBottom(force = false) {
  await nextTick()
  const element = container.value
  if (!element) return
  if (force || stickToBottom.value) {
    element.scrollTop = element.scrollHeight
  }
}

watch(
  () => props.messages.length,
  () => {
    const last = props.messages[props.messages.length - 1]
    void scrollToBottom(last?.role === 'user')
  },
)
watch(
  () => props.messages[props.messages.length - 1]?.content,
  () => {
    void scrollToBottom()
  },
)
onMounted(() => {
  void scrollToBottom(true)
})
</script>

<template>
  <div ref="container" class="messages" aria-live="polite" @scroll="onScroll">
    <article
      v-for="(message, index) in messages"
      :key="message.id"
      class="message"
      :class="`message-${message.role}`"
    >
      <div class="message-meta">
        <span>{{ message.role === 'user' ? '你' : 'CareerPilot AI' }}</span>
        <time>{{ formatTime(message.createdAt) }}</time>
      </div>
      <div class="message-body">
        {{ userFacingText(message.content)
        }}<span
          v-if="
            streaming &&
            index === messages.length - 1 &&
            message.role === 'assistant'
          "
          class="streaming-caret"
          aria-hidden="true"
        ></span>
      </div>
    </article>
  </div>
</template>