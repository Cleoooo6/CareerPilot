<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'

import type { ChatMessage } from '@/types/chat'

const props = defineProps<{ messages: ChatMessage[] }>()
const container = ref<HTMLElement | null>(null)

function formatTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

async function scrollToBottom() {
  await nextTick()
  if (container.value) container.value.scrollTop = container.value.scrollHeight
}

watch(() => props.messages.length, scrollToBottom)
onMounted(scrollToBottom)
</script>

<template>
  <div ref="container" class="messages" aria-live="polite">
    <article
      v-for="message in messages"
      :key="message.id"
      class="message"
      :class="`message-${message.role}`"
    >
      <div class="message-meta">
        <span>{{ message.role === 'user' ? '你' : 'CareerPilot' }}</span>
        <time>{{ formatTime(message.createdAt) }}</time>
      </div>
      <div class="message-body">{{ message.content }}</div>
    </article>
  </div>
</template>