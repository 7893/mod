import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import RolloutLedgerTable from '../RolloutLedgerTable.vue'
import { useProjectStore } from '../../stores/project'
import snapshotData from '../../data/fallback-snapshot.json'

// 从 snapshot 提取测试用的 entities
const mockEntities = (snapshotData as { entities?: unknown[] }).entities ?? []

function mockOrganizationsApi(filter?: (e: unknown[]) => unknown[]) {
  return vi.fn().mockImplementation((url: string) => {
    // 处理 /api/dashboard/snapshot (store refresh)
    if (url.includes('/api/dashboard/snapshot')) {
      return Promise.resolve({
        ok: true,
        json: async () => snapshotData,
      })
    }
    // 处理 /api/organizations 分页 API
    if (url.includes('/api/organizations')) {
      const urlObj = new URL(url, 'http://localhost')
      const page = Number(urlObj.searchParams.get('page') ?? 1)
      const pageSize = Number(urlObj.searchParams.get('page_size') ?? 20)
      const keyword = urlObj.searchParams.get('keyword')
      const region = urlObj.searchParams.get('region')
      const batch = urlObj.searchParams.get('batch')

      let filtered = [...mockEntities] as Array<{ name: string; owner: string; province: string; batch: string; batchId?: number }>
      if (keyword) {
        const kw = keyword.toLowerCase()
        filtered = filtered.filter(
          (e) => e.name.toLowerCase().includes(kw) || e.owner.toLowerCase().includes(kw) || e.province.toLowerCase().includes(kw)
        )
      }
      if (region) {
        filtered = filtered.filter((e) => e.province === region || e.province?.includes(region))
      }
      if (batch) {
        const batchId = Number(batch)
        filtered = filtered.filter((e) => e.batchId === batchId)
      }

      const total = filtered.length
      const start = (page - 1) * pageSize
      const items = filtered.slice(start, start + pageSize)

      return Promise.resolve({
        ok: true,
        json: async () => ({ items, total, page, page_size: pageSize }),
      })
    }
    return Promise.reject(new Error(`Unexpected fetch: ${url}`))
  })
}

describe('RolloutLedgerTable', () => {
  let store: ReturnType<typeof useProjectStore>

  beforeEach(async () => {
    setActivePinia(createPinia())
    globalThis.fetch = mockOrganizationsApi()
    store = useProjectStore()
    await flushPromises()
  })

  afterEach(() => {
    if (store) store.stopPolling()
    vi.restoreAllMocks()
  })

  it('renders entity list and option labels with counts', async () => {
    const wrapper = mount(RolloutLedgerTable)
    // 等待两轮：组件 mount + useOrganizations immediate fetch
    await flushPromises()
    await flushPromises()

    // Verify batch select has counts
    const selects = wrapper.findAll('select')
    expect(selects.length).toBe(2)
    const batchSelect = selects[0]
    const provinceSelect = selects[1]

    expect(batchSelect.text()).toContain('全部批次')
    expect(batchSelect.text()).toContain('第一批')
    expect(provinceSelect.text()).toContain('全部省份')

    // Table rows should be rendered (first page has rows)
    const rows = wrapper.findAll('tbody tr')
    expect(rows.length).toBeGreaterThan(0)
  })

  it('resets page to 1 when changing filters to prevent pagination deadlock', async () => {
    const wrapper = mount(RolloutLedgerTable)
    await flushPromises()
    await flushPromises()

    // Navigate to page 2 if totalPages > 1
    const nextBtn = wrapper.findAll('button').find((b) => b.text().includes('下一页'))
    expect(nextBtn).toBeDefined()
    await nextBtn?.trigger('click')
    await flushPromises()
    await flushPromises()

    // Find footer pagination text
    expect(wrapper.text()).toContain('第 2 /')

    // Now change batch filter to '第一批'
    const batchSelect = wrapper.findAll('select')[0]
    await batchSelect.setValue('第一批')
    await flushPromises()
    await flushPromises()

    // Page must reset to 1
    expect(wrapper.text()).toContain('第 1 /')

    // Table must not be trapped in an empty state
    const rows = wrapper.findAll('tbody tr')
    expect(rows.length).toBeGreaterThan(0)
    expect(wrapper.text()).not.toContain('无匹配单位记录')
  })

  it('shows reset button and successfully resets filters on click', async () => {
    const wrapper = mount(RolloutLedgerTable)
    await flushPromises()
    await flushPromises()

    // Initially no reset button
    let resetBtn = wrapper.findAll('button').find((b) => b.text().includes('重置'))
    expect(resetBtn).toBeUndefined()

    // Filter by province
    const provinceSelect = wrapper.findAll('select')[1]
    await provinceSelect.setValue('北京')
    await flushPromises()
    await flushPromises()

    // Subtitle shows filtered count vs total count
    expect(wrapper.text()).toContain('筛选出')
    expect(wrapper.text()).toContain(`共 ${store.entities.length} 家纳管单位`)

    // Reset button appears
    resetBtn = wrapper.findAll('button').find((b) => b.text().includes('重置'))
    expect(resetBtn).toBeDefined()

    // Click reset
    await resetBtn?.trigger('click')
    await flushPromises()
    await flushPromises()

    // Back to original state - all entities returned
    expect(wrapper.text()).toContain('家纳管单位')
    expect(wrapper.findAll('button').find((b) => b.text().includes('重置'))).toBeUndefined()
  })

  it('allows clearing filters from the empty state if nothing matches', async () => {
    const wrapper = mount(RolloutLedgerTable)
    await flushPromises()
    await flushPromises()

    const input = wrapper.find('input')
    await input.setValue('THIS_STRING_DOES_NOT_EXIST_XYZ_123')
    await flushPromises()
    await flushPromises()

    expect(wrapper.text()).toContain('无匹配单位记录')
    const clearBtn = wrapper.findAll('button').find((b) => b.text().includes('清除筛选条件并返回全部'))
    expect(clearBtn).toBeDefined()

    await clearBtn?.trigger('click')
    await flushPromises()
    await flushPromises()

    expect(wrapper.text()).not.toContain('无匹配单位记录')
    expect(wrapper.findAll('tbody tr').length).toBeGreaterThan(0)
  })
})
