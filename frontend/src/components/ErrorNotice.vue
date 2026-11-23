<script setup lang="ts">
import type { ChatError } from '@/types/chat'

defineProps<{ error: ChatError }>()
defineEmits<{ dismiss: [] }>()
</script>

<template>
  <div class="error-notice" role="alert">
    <div>
      <strong>本次请求失败</strong>
      <p>{{ error.message }}</p>
      <code>{{ error.code }}</code>
    </div>
    <button type="button" class="button ghost" @click="$emit('dismiss')">关闭</button>
  </div>
</template>