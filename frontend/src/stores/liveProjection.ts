import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { LiveProjectionCounts, LiveProjectionEvent } from '../composables/useLiveProjection'
import { useProjectStore } from './project'

export const useLiveProjectionStore = defineStore('live-projection', () => {
  const project = useProjectStore()
  const cumulative = ref<LiveProjectionCounts>({ documents: 0, vouchers: 0, integrations: 0 })
  const projectionId = ref('')
  const sequence = ref(0)

  const liveOverview = computed(() => {
    // The snapshot already reads the same committed database facts. SSE cumulative
    // values are a session pulse only and must never be overlaid onto authoritative totals.
    return project.snapshot.overview
  })

  function apply(event: LiveProjectionEvent) {
    if (event.resetRequired) {
      void project.refresh(true)
    }
    if (event.resetRequired || projectionId.value !== event.projectionId) {
      projectionId.value = event.projectionId
      sequence.value = 0
      cumulative.value = { documents: 0, vouchers: 0, integrations: 0 }
    }
    if (event.sequence <= sequence.value) return false
    sequence.value = event.sequence
    cumulative.value = { ...event.cumulative }
    return true
  }

  return { cumulative, liveOverview, apply }
})
