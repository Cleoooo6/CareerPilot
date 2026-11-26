<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'

import AppLayout from '@/layouts/AppLayout.vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const auth = useAuthStore()
const isAuthLayout = computed(() => route.meta.layout === 'auth')
const isBooting = computed(() => auth.status === 'unknown')
</script>

<template>
  <RouterView v-if="isAuthLayout" />
  <div v-else-if="isBooting" class="app-boot-splash" aria-hidden="true"></div>
  <AppLayout v-else>
    <RouterView />
  </AppLayout>
</template>

<style scoped>
.app-boot-splash {
  min-height: 100vh;
  background: var(--bg);
}
</style>