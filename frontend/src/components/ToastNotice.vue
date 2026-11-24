<script setup lang="ts">
import { onMounted, onUnmounted, watch } from 'vue'

const props = defineProps<{ message: string }>()
const emit = defineEmits<{ close: [] }>()

let timer: ReturnType<typeof setTimeout> | undefined

function schedule() {
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => emit('close'), 3200)
}

onMounted(schedule)
onUnmounted(() => {
  if (timer) clearTimeout(timer)
})
watch(() => props.message, schedule)
</script>

<template>
  <div class="toast" role="status">{{ message }}</div>
</template>