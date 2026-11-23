<script setup lang="ts">
import { computed, ref } from 'vue'

const props = defineProps<{ streaming: boolean }>()
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

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    submit()
  }
}
</script>

<template>
  <div class="composer">
    <textarea
      v-model="draft"
      class="composer-input"
      rows="2"
      maxlength="4000"
      :disabled="streaming"
      placeholder="说说你现在的方向、困惑或目标…"
      aria-label="消息输入框"
      @keydown="onKeydown"
    ></textarea>
    <div class="composer-actions">
      <span class="composer-hint">Enter 发送 · Shift + Enter 换行</span>
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
  </div>
</template>