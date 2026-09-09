import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ConstructionLedger from '../ConstructionLedger.vue'
import { useProjectStore } from '../../stores/project'
import snapshotData from '../../data/v2-sim-snapshot.json'

describe('ConstructionLedger', () => {
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

  it('renders B6, B7, B8 zones and filter options with counts', async () => {
    const wrapper = mount(ConstructionLedger)
    await flushPromises()

    // Panel zones B6, B7, B8
    expect(wrapper.find('[data-zone="B6"]').exists()).toBe(true)
    expect(wrapper.find('[data-zone="B7"]').exists()).toBe(true)
    expect(wrapper.find('[data-zone="B8"]').exists()).toBe(true)

    // Select options with counts: batch (0), province (1), lifecycle (2), readiness (3)
    const selects = wrapper.findAll('select')
    expect(selects[0].text()).toContain('全部批次')
    expect(selects[1].text()).toContain('全部省份')
    expect(selects[2].text()).toContain('全部状态')
    expect(selects[2].text()).toContain('准备中')
    expect(selects[3].text()).toContain('全部准备度')

    // Page 2
    const nextBtn = wrapper.findAll('button').find((b) => b.text().includes('下一页'))
    await nextBtn?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('第 2 /')

    // Change batch (select[0])
    await selects[0].setValue('第一批')
    await flushPromises()

    // Resets to page 1
    expect(wrapper.text()).toContain('第 1 /')
    expect(wrapper.findAll('tbody tr').length).toBeGreaterThan(0)
  })

  it('keeps data-readiness filtering independent from lifecycle status', async () => {
    store.entities = [
      { ...store.entities[0], id: 1, name: '已校验单位', status: '建设中', readinessStatus: '已校验' },
      { ...store.entities[1], id: 2, name: '收集中单位', status: '建设中', readinessStatus: '收集中' },
    ]
    const wrapper = mount(ConstructionLedger, {
      props: { initialReadinessFilter: '已校验' },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('已校验单位')
    expect(wrapper.text()).not.toContain('收集中单位')
    expect(wrapper.findAll('select')[2].element.value).toBe('全部')
    expect(wrapper.findAll('select')[3].element.value).toBe('已校验')
  })

  it('supports filter reset via toolbar reset button', async () => {
    const wrapper = mount(ConstructionLedger)
    await flushPromises()

    const provinceSelect = wrapper.findAll('select')[1]
    await provinceSelect.setValue('北京')
    await flushPromises()

    const resetBtn = wrapper.findAll('button').find((b) => b.text().includes('重置'))
    expect(resetBtn).toBeDefined()
    await resetBtn?.trigger('click')
    await flushPromises()

    expect(wrapper.findAll('button').find((b) => b.text().includes('重置'))).toBeUndefined()
  })

  it('supports filtering by status and searching by ID or name', async () => {
    const wrapper = mount(ConstructionLedger)
    await flushPromises()

    const statusSelect = wrapper.findAll('select')[2]
    await statusSelect.setValue('已上线')
    await flushPromises()

    const rows = wrapper.findAll('tbody tr')
    expect(rows.length).toBeGreaterThan(0)
    for (const row of rows) {
      expect(row.text()).toContain('已上线')
    }

    // Search by ID
    const searchInput = wrapper.find('input[placeholder*="搜索单位"]')
    await searchInput.setValue('MOD-1')
    await flushPromises()

    const searchRows = wrapper.findAll('tbody tr')
    expect(searchRows.length).toBeGreaterThan(0)
  })
})
