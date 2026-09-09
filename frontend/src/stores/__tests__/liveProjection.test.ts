import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'
import { useLiveProjectionStore } from '../liveProjection'
import { useProjectStore } from '../project'
import type { LiveProjectionEvent } from '../../composables/useLiveProjection'
import snapshotData from '../../data/v2-sim-snapshot.json'

function makeEvent(patch: Partial<LiveProjectionEvent>): LiveProjectionEvent {
  return {
    id: 'evt-1',
    sequence: 1,
    occurredAt: '2026-09-06T10:00:00Z',
    businessType: 'document_created',
    increments: { documents: 1, vouchers: 1, integrations: 0 },
    cumulative: { documents: 1, vouchers: 1, integrations: 0 },
    projectionId: 'proj-001',
    mode: 'committed_simulation',
    ...patch,
  }
}

describe('stores/liveProjection', () => {
  let projectStore: ReturnType<typeof useProjectStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => snapshotData,
    })
  })

  afterEach(() => {
    if (projectStore) {
      projectStore.stopPolling()
    }
    vi.restoreAllMocks()
  })

  it('initializes with zero cumulative counts and empty projectionId', async () => {
    const store = useLiveProjectionStore()
    projectStore = useProjectStore()
    await flushPromises()
    expect(store.cumulative).toEqual({ documents: 0, vouchers: 0, integrations: 0 })
  })

  it('applies a valid live projection event and increments cumulative counts', async () => {
    const store = useLiveProjectionStore()
    projectStore = useProjectStore()
    await flushPromises()

    store.apply(
      makeEvent({
        projectionId: 'proj-001',
        sequence: 1,
        cumulative: { documents: 12, vouchers: 8, integrations: 3 },
      })
    )

    expect(store.cumulative).toEqual({ documents: 12, vouchers: 8, integrations: 3 })
  })

  it('discards out-of-order or duplicate sequence events', async () => {
    const store = useLiveProjectionStore()
    projectStore = useProjectStore()
    await flushPromises()

    store.apply(
      makeEvent({
        projectionId: 'proj-001',
        sequence: 5,
        cumulative: { documents: 20, vouchers: 15, integrations: 5 },
      })
    )
    expect(store.cumulative.documents).toBe(20)

    // Event with sequence 4 (stale) should be ignored
    store.apply(
      makeEvent({
        projectionId: 'proj-001',
        sequence: 4,
        cumulative: { documents: 18, vouchers: 12, integrations: 4 },
      })
    )
    expect(store.cumulative.documents).toBe(20)

    // Event with sequence 5 (duplicate) should be ignored
    store.apply(
      makeEvent({
        projectionId: 'proj-001',
        sequence: 5,
        cumulative: { documents: 22, vouchers: 16, integrations: 5 },
      })
    )
    expect(store.cumulative.documents).toBe(20)
  })

  it('resets cumulative counts when projectionId changes', async () => {
    const store = useLiveProjectionStore()
    projectStore = useProjectStore()
    await flushPromises()

    store.apply(
      makeEvent({
        projectionId: 'proj-001',
        sequence: 10,
        cumulative: { documents: 50, vouchers: 40, integrations: 10 },
      })
    )
    expect(store.cumulative.documents).toBe(50)

    // New projection session
    store.apply(
      makeEvent({
        projectionId: 'proj-002',
        sequence: 1,
        cumulative: { documents: 2, vouchers: 1, integrations: 0 },
      })
    )
    expect(store.cumulative).toEqual({ documents: 2, vouchers: 1, integrations: 0 })
  })

  it('never double-counts the committed SSE pulse on top of the database snapshot', async () => {
    projectStore = useProjectStore()
    const liveStore = useLiveProjectionStore()
    await flushPromises()

    const initialDocsTotal = projectStore.snapshot.overview.docsTotal
    const initialDocsToday = projectStore.snapshot.overview.docsTodayAdded
    const initialVouchersTotal = projectStore.snapshot.overview.vouchersTotal
    const initialVouchersToday = projectStore.snapshot.overview.vouchersTodayAdded

    liveStore.apply(
      makeEvent({
        projectionId: 'proj-001',
        sequence: 1,
        cumulative: { documents: 25, vouchers: 14, integrations: 6 },
      })
    )

    const overview = liveStore.liveOverview
    expect(overview.docsTotal).toBe(initialDocsTotal)
    expect(overview.docsTodayAdded).toBe(initialDocsToday)
    expect(overview.vouchersTotal).toBe(initialVouchersTotal)
    expect(overview.vouchersTodayAdded).toBe(initialVouchersToday)
  })
})
