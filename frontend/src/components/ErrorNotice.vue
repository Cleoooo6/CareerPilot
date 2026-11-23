<script setup lang="ts">
import type { ChatError } from '@/types/chat'

defineProps<{ error: ChatError }>()
defineEmits<{ dismiss: [] }>()
</script>

<template>
  <div class="error-notice" role="alert">
    <div>
      <strong>暂时无法完成操作</strong>
      <p>{{ error.message }}</p>
    </div>
    <button type="button" class="button ghost small" @click="$emit('dismiss')">
      关闭
    </button>
  </div>
</template>