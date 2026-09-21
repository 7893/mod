import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { LiveProjectionCounts, LiveProjectionEvent } from '../composables/useLiveProjection'
import { useProjectStore } from './project'

export const useLiveProjectionStore = defineStore('live-projection', () => {
  const project = useProjectStore()
  const cumulative = ref<LiveProjectionCounts>({ documents: 0, vouchers: 0, integrations: 0 })
  const pendingPulses = ref<Array<{ occurredAt: number, increments: LiveProjectionCounts }>>([])
  const projectionId = ref('')
  const sequence = ref(0)

  const snapshotTimestamp = () => Date.parse(project.snapshot.meta.generatedAt || '')

  const liveOverview = computed(() => {
    const overview = project.snapshot.overview
    const snapshotAt = snapshotTimestamp()
    if (!Number.isFinite(snapshotAt)) return overview

    const pending = pendingPulses.value.reduce<LiveProjectionCounts>((total, pulse) => {
      if (pulse.occurredAt <= snapshotAt) return total
      total.documents += pulse.increments.documents
      total.vouchers += pulse.increments.vouchers
      total.integrations += pulse.increments.integrations
      return total
    }, { documents: 0, vouchers: 0, integrations: 0 })

    return {
      ...overview,
      docsTodayAdded: overview.docsTodayAdded + pending.documents,
      vouchersTodayAdded: overview.vouchersTodayAdded + pending.vouchers,
    }
  })

  function apply(event: LiveProjectionEvent) {
    if (event.resetRequired) {
      void project.refresh(true)
    }
    if (event.resetRequired || projectionId.value !== event.projectionId) {
      projectionId.value = event.projectionId
      sequence.value = 0
      cumulative.value = { documents: 0, vouchers: 0, integrations: 0 }
      pendingPulses.value = []
    }
    if (event.sequence <= sequence.value) return false
    sequence.value = event.sequence
    cumulative.value = { ...event.cumulative }
    if (event.businessType !== 'projection_state') {
      const occurredAt = Date.parse(event.occurredAt)
      const snapshotAt = snapshotTimestamp()
      if (Number.isFinite(occurredAt) && Number.isFinite(snapshotAt) && occurredAt > snapshotAt) {
        pendingPulses.value = [
          ...pendingPulses.value.filter((pulse) => pulse.occurredAt > snapshotAt),
          { occurredAt, increments: { ...event.increments } },
        ].slice(-2000)
      }
    }
    return true
  }

  return { cumulative, liveOverview, apply }
})
