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

  it('renders filter options with counts and resets page on filter change', async () => {
    const wrapper = mount(ConstructionLedger)
    await flushPromises()

    // Page 2
    const nextBtn = wrapper.findAll('button').find((b) => b.text().includes('下一页'))
    await nextBtn?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('第 2 /')

    // Change batch
    const batchSelect = wrapper.findAll('select')[1]
    await batchSelect.setValue('第一批')
    await flushPromises()

    // Resets to page 1
    expect(wrapper.text()).toContain('第 1 /')
    expect(wrapper.findAll('tbody tr').length).toBeGreaterThan(0)
  })

  it('supports filter reset via toolbar reset button', async () => {
    const wrapper = mount(ConstructionLedger)
    await flushPromises()

    const provinceSelect = wrapper.findAll('select')[2]
    await provinceSelect.setValue('北京')
    await flushPromises()

    const resetBtn = wrapper.findAll('button').find((b) => b.text().includes('重置'))
    expect(resetBtn).toBeDefined()
    await resetBtn?.trigger('click')
    await flushPromises()

    expect(wrapper.findAll('button').find((b) => b.text().includes('重置'))).toBeUndefined()
  })
})
