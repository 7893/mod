import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'
import { useProjectStore } from '../project'
import snapshotData from '../../data/v2-sim-snapshot.json'

describe('stores/project', () => {
  let store: ReturnType<typeof useProjectStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => snapshotData,
    })
  })

  afterEach(() => {
    if (store) {
      store.stopPolling()
    }
    vi.restoreAllMocks()
  })

  it('initializes with valid baseline snapshot data and entities', async () => {
    store = useProjectStore()
    await flushPromises()

    expect(store.snapshot).toBeDefined()
    expect(store.snapshot.overview).toBeDefined()
    expect(store.snapshot.overview.docsTotal).toBeGreaterThan(0)
    expect(store.entities.length).toBeGreaterThan(0)
    expect(store.connectionError).toBe('')
    expect(store.loading).toBe(false)
  })

  it('calculates statusCount correctly based on entities', async () => {
    store = useProjectStore()
    await flushPromises()

    const counts = store.statusCount
    const totalFromCounts = Object.values(counts).reduce((a, b) => a + b, 0)
    expect(totalFromCounts).toBe(store.entities.length)
  })

  it('updates an entity and records an audit log entry', async () => {
    store = useProjectStore()
    await flushPromises()

    const target = store.entities[0]
    const originalStatus = target.status
    const newStatus = originalStatus === '已上线' ? '双轨运行' : '已上线'
    const initialAuditsLength = store.audits.length

    store.updateEntity(target.id, { status: newStatus as any })

    expect(target.status).toBe(newStatus)
    expect(target.updatedAt).toBe('刚刚')
    expect(store.audits.length).toBe(initialAuditsLength + 1)
    expect(store.audits[0].entity).toBe(target.name)
    expect(store.audits[0].field).toBe('上线状态')
    expect(store.audits[0].before).toBe(originalStatus)
    expect(store.audits[0].after).toBe(newStatus)
  })

  it('refreshes snapshot from API, transforms snake_case to camelCase, and handles success', async () => {
    store = useProjectStore()
    await flushPromises()

    const mockApiResponse = {
      overview: {
        docs_total: 9999999,
        docs_today_added: 12345,
        vouchers_total: 8888888,
        vouchers_today_added: 9876,
        as_of_date: '2026-09-06',
        launched: 500,
        launched_pct: 25.0,
      },
      entities: [
        {
          id: 1,
          province: '北京',
          name: '新测试单位',
          batch: '第一批',
          owner: '张三',
          status: '已上线',
          construction: 100,
          opening_data: 100,
          voucher_rate: 99.5,
          updated_at: '2026-09-06',
        },
      ],
    }

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockApiResponse,
    })

    await store.refresh()

    expect(store.snapshot.overview.docsTotal).toBe(9999999)
    expect(store.snapshot.overview.docsTodayAdded).toBe(12345)
    expect(store.snapshot.overview.vouchersTotal).toBe(8888888)
    expect(store.snapshot.overview.asOfDate).toBe('2026-09-06')
    expect(store.entities[0].name).toBe('新测试单位')
    expect(store.entities[0].openingData).toBe(100)
    expect(store.connectionError).toBe('')
    expect(store.loading).toBe(false)
  })

  it('gracefully handles network error on refresh and maintains previous snapshot', async () => {
    store = useProjectStore()
    await flushPromises()
    const previousDocsTotal = store.snapshot.overview.docsTotal

    globalThis.fetch = vi.fn().mockRejectedValue(new Error('Gateway timeout'))

    await store.refresh()

    expect(store.loading).toBe(false)
    expect(store.connectionError).toContain('数据刷新受阻（Gateway timeout），当前维持上一有效快照')
    expect(store.snapshot.overview.docsTotal).toBe(previousDocsTotal)
  })
})
