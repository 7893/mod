import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import RolloutLedgerTable from '../RolloutLedgerTable.vue'
import { useProjectStore } from '../../stores/project'
import snapshotData from '../../data/fallback-snapshot.json'

describe('RolloutLedgerTable', () => {
  let store: ReturnType<typeof useProjectStore>

  beforeEach(async () => {
    setActivePinia(createPinia())
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => snapshotData,
    })
    store = useProjectStore()
    await flushPromises()
  })

  afterEach(() => {
    if (store) store.stopPolling()
    vi.restoreAllMocks()
  })

  it('renders entity list and option labels with counts', async () => {
    const wrapper = mount(RolloutLedgerTable)
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

    // Navigate to page 2 if totalPages > 1
    const nextBtn = wrapper.findAll('button').find((b) => b.text().includes('下一页'))
    expect(nextBtn).toBeDefined()
    await nextBtn?.trigger('click')
    await flushPromises()

    // Find footer pagination text
    expect(wrapper.text()).toContain('第 2 /')

    // Now change batch filter to '第一批'
    const batchSelect = wrapper.findAll('select')[0]
    await batchSelect.setValue('第一批')
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

    // Initially no reset button
    let resetBtn = wrapper.findAll('button').find((b) => b.text().includes('重置'))
    expect(resetBtn).toBeUndefined()

    // Filter by province
    const provinceSelect = wrapper.findAll('select')[1]
    await provinceSelect.setValue('北京')
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

    // Back to original state
    expect(wrapper.text()).toContain(`共 ${store.entities.length} 家纳管单位`)
    expect(wrapper.findAll('button').find((b) => b.text().includes('重置'))).toBeUndefined()
  })

  it('allows clearing filters from the empty state if nothing matches', async () => {
    const wrapper = mount(RolloutLedgerTable)
    await flushPromises()

    const input = wrapper.find('input')
    await input.setValue('THIS_STRING_DOES_NOT_EXIST_XYZ_123')
    await flushPromises()

    expect(wrapper.text()).toContain('无匹配单位记录')
    const clearBtn = wrapper.findAll('button').find((b) => b.text().includes('清除筛选条件并返回全部'))
    expect(clearBtn).toBeDefined()

    await clearBtn?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).not.toContain('无匹配单位记录')
    expect(wrapper.findAll('tbody tr').length).toBeGreaterThan(0)
  })
})
