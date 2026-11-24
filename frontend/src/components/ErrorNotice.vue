<script setup lang="ts">
import type { ChatError } from '@/types/chat'

defineProps<{ error: ChatError; retryable?: boolean }>()
defineEmits<{ dismiss: []; retry: [] }>()
</script>

<template>
  <div class="error-notice" role="alert">
    <div>
      <strong>暂时无法完成操作</strong>
      <p>{{ error.message }}</p>
    </div>
    <div class="composer-buttons">
      <button type="button" class="button ghost small" @click="$emit('dismiss')">
        关闭
      </button>
      <button
        v-if="retryable"
        type="button"
        class="button small"
        @click="$emit('retry')"
      >
        重试
      </button>
    </div>
  </div>
</template>