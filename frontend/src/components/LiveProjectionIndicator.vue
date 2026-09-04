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
