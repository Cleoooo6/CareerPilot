<script setup lang="ts">
import type { TimelineItem } from '@/types/chat'

defineProps<{ items: TimelineItem[] }>()

function label(status: TimelineItem['status']): string {
  if (status === 'running') return '执行中'
  if (status === 'failed') return '失败'
  return '已完成'
}
</script>

<template>
  <section class="timeline" aria-label="Agent 执行过程">
    <div class="timeline-head">
      <span class="timeline-title">执行过程</span>
      <span class="timeline-hint">SSE · 节点级 Trace</span>
    </div>
    <ol class="timeline-list">
      <li
        v-for="item in items"
        :key="item.node"
        class="timeline-item"
        :data-status="item.status"
      >
        <span class="timeline-dot"></span>
        <span class="timeline-node">{{ item.node }}</span>
        <span class="timeline-state">{{ label(item.status) }}</span>
      </li>
    </ol>
  </section>
</template>