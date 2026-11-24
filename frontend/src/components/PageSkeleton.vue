<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: 'dashboard' | 'profile' | 'market' | 'roadmap'
  }>(),
  { variant: 'profile' },
)
</script>

<template>
  <div class="skeleton-page" aria-busy="true" aria-label="正在加载">
    <template v-if="variant === 'dashboard'">
      <div class="skeleton skeleton-line lg"></div>
      <div class="skeleton skeleton-line sm"></div>
      <div class="skeleton skeleton-block"></div>
      <div class="skeleton-grid">
        <div class="skeleton skeleton-card"></div>
        <div class="skeleton skeleton-card"></div>
        <div class="skeleton skeleton-card"></div>
      </div>
    </template>
    <template v-else-if="variant === 'market'">
      <div class="skeleton skeleton-line lg"></div>
      <div class="skeleton skeleton-line sm"></div>
      <div class="skeleton-grid">
        <div class="skeleton skeleton-card"></div>
        <div class="skeleton skeleton-card"></div>
        <div class="skeleton skeleton-card"></div>
      </div>
      <div class="skeleton skeleton-block"></div>
      <div class="skeleton skeleton-block" style="height: 180px"></div>
    </template>
    <template v-else-if="variant === 'roadmap'">
      <div class="skeleton skeleton-line lg"></div>
      <div class="skeleton skeleton-line sm"></div>
      <div class="skeleton skeleton-block" style="height: 180px"></div>
      <div class="skeleton skeleton-block"></div>
      <div class="skeleton skeleton-row">
        <div class="skeleton skeleton-line md"></div>
      </div>
    </template>
    <template v-else>

      <div class="skeleton-tabs">
        <div v-for="index in 5" :key="index" class="skeleton skeleton-tab"></div>
      </div>
      <div class="skeleton skeleton-block"></div>
    </template>
  </div>
</template>