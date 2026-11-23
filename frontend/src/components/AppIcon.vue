<script setup lang="ts">
withDefaults(
  defineProps<{
    name: 'chat' | 'profile' | 'market' | 'roadmap' | 'dashboard'
    size?: number
  }>(),
  { size: 18 },
)
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.7"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <template v-if="name === 'chat'">
      <path d="M21 11.5a8.4 8.4 0 0 1-8.8 8.4 8.7 8.7 0 0 1-3.9-.9L3 21l1.9-4.9A8.4 8.4 0 1 1 21 11.5Z" />
    </template>
    <template v-else-if="name === 'profile'">
      <circle cx="12" cy="8" r="3.4" />
      <path d="M5 20a7 7 0 0 1 14 0" />
    </template>
    <template v-else-if="name === 'market'">
      <path d="M4 19V9M10 19V5M16 19v-6M22 19H2" />
    </template>
    <template v-else-if="name === 'roadmap'">
      <circle cx="6" cy="19" r="2" />
      <circle cx="18" cy="5" r="2" />
      <path d="M8 19h5a4 4 0 0 0 0-8H9a4 4 0 0 1 0-8h7" />
    </template>
    <template v-else>
      <rect x="3" y="3" width="7" height="7" rx="1.6" />
      <rect x="14" y="3" width="7" height="7" rx="1.6" />
      <rect x="3" y="14" width="7" height="7" rx="1.6" />
      <rect x="14" y="14" width="7" height="7" rx="1.6" />
    </template>
  </svg>
</template>