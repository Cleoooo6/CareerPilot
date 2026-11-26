<script setup lang="ts">
import { computed, ref } from 'vue'

const props = defineProps<{ streaming: boolean; hint?: string }>()
const emit = defineEmits<{
  send: [content: string]
  stop: []
}>()

const draft = ref('')
const canSend = computed(() => draft.value.trim().length > 0 && !props.streaming)

function submit() {
  if (!canSend.value) return
  emit('send', draft.value.trim())
  draft.value = ''
}

function fill(text: string) {
  draft.value = text
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    submit()
  }
}

defineExpose({ fill })
</script>

<template>
  <div class="composer">
    <div class="composer-shell">
      <label class="composer-label" for="chat-message-input">你的问题</label>
      <textarea
        id="chat-message-input"
        v-model="draft"
        class="composer-input"
        rows="2"
        maxlength="4000"
        :disabled="streaming"
        placeholder="问问你的职业规划，比如：我适不适合走 AI 应用开发？"
        aria-label="消息输入框"
        @keydown="onKeydown"
      ></textarea>
      <div class="composer-actions">
        <span class="composer-hint">
          {{ canSend ? 'Enter 发送 · Shift + Enter 换行' : '输入内容后可发送' }}
        </span>
        <div class="composer-buttons">
          <button
            v-if="streaming"
            type="button"
            class="button ghost"
            @click="emit('stop')"
          >
            停止
          </button>
          <button
            type="button"
            class="button primary"
            :disabled="!canSend"
            @click="submit"
          >
            发送
          </button>
        </div>
      </div>
      <p class="composer-help">
        {{ hint || '回答中的判断会标注「AI 推断 / AI 建议」；涉及画像时会注明来源。' }}
      </p>
    </div>
  </div>
</template>