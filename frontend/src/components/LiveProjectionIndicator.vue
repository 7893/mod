<script setup lang="ts">
import { computed } from 'vue'
import type { LiveProjectionEvent } from '../composables/useLiveProjection'

const props = defineProps<{
  connected: boolean
  event: LiveProjectionEvent | null
}>()

const pulseText = computed(() => {
  if (props.event?.increments.documents) return `单据 +${props.event.increments.documents}`
  if (props.event?.increments.vouchers) return `凭证 +${props.event.increments.vouchers}`
  if (props.event?.increments.integrations) return `集成 +${props.event.increments.integrations}`
  return ''
})
</script>

<template>
  <div class="projection-indicator" :class="{ 'projection-indicator--connected': connected }">
    <span class="projection-indicator__dot"></span>
    <span>演示动态</span>
    <Transition name="projection-pulse">
      <b v-if="pulseText" :key="event?.id">刚刚 {{ pulseText }}</b>
    </Transition>
  </div>
</template>

<style scoped>
.projection-indicator {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  color: var(--c-text-muted);
  font-size: var(--text-xxs);
}

.projection-indicator__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--c-text-dim);
}

.projection-indicator--connected .projection-indicator__dot {
  background: var(--c-success);
  box-shadow: 0 0 8px rgb(45 212 160 / 65%);
}

.projection-indicator b {
  margin-left: var(--space-2);
  color: var(--c-success);
  font-family: var(--font-mono);
  font-weight: 600;
}

.projection-pulse-enter-active,
.projection-pulse-leave-active {
  transition: opacity 220ms ease, transform 220ms ease;
}

.projection-pulse-enter-from,
.projection-pulse-leave-to {
  opacity: 0;
  transform: translateY(4px);
}
</style>
