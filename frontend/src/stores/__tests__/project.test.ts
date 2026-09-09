import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'
import { useProjectStore } from '../project'
import snapshotData from '../../data/v2-sim-snapshot.json'
import { calcDualRunConsistency } from '../../utils/qualityMetrics'

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

  it('never shows loading spinner while snapshot request is pending (KI-059 no-spinner)', async () => {
    // 后端快照即使冷启动 >1s，只要已有兜底/上一份快照可展示，前台就绝不转圈。
    let resolveFetch: (value: unknown) => void = () => {}
    const pending = new Promise((resolve) => {
      resolveFetch = resolve
    })
    globalThis.fetch = vi.fn().mockReturnValue(pending)

    store = useProjectStore()
    // 初始已用内置兜底快照预填，entities 非空
    expect(store.entities.length).toBeGreaterThan(0)

    // 主动触发一次非 silent 刷新，模拟首屏加载；请求仍在途中
    const refreshPromise = store.refresh()
    await flushPromises()

    // 关键断言：请求 pending 期间 loading 始终为 false（顶栏不转圈、内容区照常展示兜底数据）
    expect(store.loading).toBe(false)

    // 请求返回后仍不转圈
    resolveFetch({ ok: true, json: async () => snapshotData })
    await refreshPromise
    await flushPromises()
    expect(store.loading).toBe(false)
    expect(store.entities.length).toBeGreaterThan(0)
  })

  it('provides complete contract for C3 rolloutTrend, D3 operationsTrend, and D6 dualRun (KI-061)', async () => {
    store = useProjectStore()
    await flushPromises()

    // C3: 批次历程走势
    expect(store.snapshot.rolloutTrend).toBeDefined()
    expect(store.snapshot.rolloutTrend!.length).toBeGreaterThan(0)
    const firstRt = store.snapshot.rolloutTrend![0]
    expect(firstRt.date).toBeDefined()
    expect(firstRt.batchId).toBeGreaterThan(0)
    expect(typeof firstRt.launchedPct).toBe('number')

    // D3: 日均吞吐趋势
    expect(store.snapshot.operationsTrend).toBeDefined()
    expect(store.snapshot.operationsTrend!.length).toBeGreaterThan(0)
    const firstOt = store.snapshot.operationsTrend![0]
    expect(firstOt.date).toBeDefined()
    expect(firstOt.documents).toBeDefined()

    // D6: 双轨运行核对
    const ops = store.snapshot.operations
    expect(ops.dualRunConsistent).toBeDefined()
    expect(ops.dualRunInconsistent).toBeDefined()
    expect(ops.dualRunConsistent!).toBeGreaterThan(0)
    expect(ops.dualRunResult).toBeGreaterThan(0)

    const dualStats = calcDualRunConsistency(
      ops.dualRunResult,
      ops.dualRunConsistent,
      ops.dualRunInconsistent,
    )
    expect(dualStats).not.toBeNull()
    expect(dualStats!.consistent).toBe(ops.dualRunConsistent)
    expect(dualStats!.consistencyPct).toBeGreaterThanOrEqual(90)

    if (ops.dualRunBreakdown) {
      expect(Array.isArray(ops.dualRunBreakdown)).toBe(true)
      for (const item of ops.dualRunBreakdown) {
        expect(item.type).toBeDefined()
        expect(item.consistent).toBeGreaterThanOrEqual(0)
        expect(item.inconsistent).toBeGreaterThanOrEqual(0)
        expect(item.rate).toBeGreaterThanOrEqual(0)
      }
    }
  })
})
