import { effectScope, nextTick, ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useProjectStore, type EntityRow } from '../../stores/project.ts'
import { useEntityLedger } from '../useEntityLedger.ts'

const rows: EntityRow[] = [
  { id: 1, name: '北京一部', province: '北京', batch: '第一批', owner: '张三', status: '已上线', construction: 100, openingData: 100, readinessStatus: '已校验', voucherRate: 99, updatedAt: '—' },
  { id: 2, name: '上海二部', province: '上海', batch: '第二批', owner: '李四', status: '双轨运行', construction: 90, openingData: 80, readinessStatus: '收集中', voucherRate: 95, updatedAt: '—' },
]

describe('useEntityLedger', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('filters and paginates the shared project-store projection without list requests', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 }))
    setActivePinia(createPinia())
    const store = useProjectStore()
    store.entities = rows
    const province = ref('北京')
    const query = ref('')
    const scope = effectScope()
    const ledger = scope.run(() => useEntityLedger({ pageSize: 1, province, query }))!

    expect(ledger.total.value).toBe(1)
    expect(ledger.items.value[0]?.name).toBe('北京一部')

    province.value = '全部'
    query.value = 'MOD-2'
    await nextTick()

    expect(ledger.total.value).toBe(1)
    expect(ledger.items.value[0]?.name).toBe('上海二部')
    const requestedUrls = vi.mocked(globalThis.fetch).mock.calls.map(([url]) => String(url))
    expect(requestedUrls.some((url) => url.includes('/api/organizations?'))).toBe(false)
    scope.stop()
    store.stopPolling()
  })
})
