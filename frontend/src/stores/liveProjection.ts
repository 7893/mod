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
    const now = new Date()
    const year = now.getFullYear()
    const month = String(now.getMonth() + 1).padStart(2, '0')
    const day = String(now.getDate()).padStart(2, '0')
    const localDateStr = `${year}-${month}-${day}`

    const baseDocDate = project.snapshot.overview.docsAddedAsOfDate || localDateStr
    const effectiveDocDate = baseDocDate > localDateStr ? baseDocDate : localDateStr

    const baseVoucherDate = project.snapshot.overview.vouchersAddedAsOfDate || localDateStr
    const effectiveVoucherDate = baseVoucherDate > localDateStr ? baseVoucherDate : localDateStr

    return {
      ...project.snapshot.overview,
      docsTotal: project.snapshot.overview.docsTotal + cumulative.value.documents,
      docsTodayAdded: project.snapshot.overview.docsTodayAdded + cumulative.value.documents,
      vouchersTotal: project.snapshot.overview.vouchersTotal + cumulative.value.vouchers,
      vouchersTodayAdded: project.snapshot.overview.vouchersTodayAdded + cumulative.value.vouchers,
      docsAddedAsOfDate: effectiveDocDate,
      vouchersAddedAsOfDate: effectiveVoucherDate,
    }
  })

  function apply(event: LiveProjectionEvent) {
    if (projectionId.value !== event.projectionId) {
      projectionId.value = event.projectionId
      sequence.value = 0
      cumulative.value = { documents: 0, vouchers: 0, integrations: 0 }
    }
    if (event.sequence <= sequence.value) return
    sequence.value = event.sequence
    cumulative.value = { ...event.cumulative }
  }

  return { cumulative, liveOverview, apply }
})
