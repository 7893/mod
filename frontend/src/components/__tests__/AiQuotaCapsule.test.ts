import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import AiQuotaCapsule from '../AiQuotaCapsule.vue'

describe('AiQuotaCapsule', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders quota usage and zero-cost guarantee badge', async () => {
    const mockData = {
      statDate: '2026-09-08',
      callCount: 3,
      neuronsUsed: 12.5,
      dailyLimit: 3000,
      remainingNeurons: 2987.5,
      usagePct: 0.42,
      status: 'ACTIVE',
    }

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockData),
      })
    )

    const wrapper = mount(AiQuotaCapsule)
    await flushPromises()

    expect(wrapper.text()).toContain('CF AI')
    expect(wrapper.text()).toContain('12.5')
    expect(wrapper.text()).toContain('3000')
    expect(wrapper.text()).toContain('$0.00保障')
  })

  it('renders fused state badge when quota is exhausted', async () => {
    const mockFused = {
      statDate: '2026-09-08',
      callCount: 50,
      neuronsUsed: 3050.0,
      dailyLimit: 3000,
      remainingNeurons: 0.0,
      usagePct: 100.0,
      status: 'FUSED',
    }

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockFused),
      })
    )

    const wrapper = mount(AiQuotaCapsule)
    await flushPromises()

    expect(wrapper.text()).toContain('已熔断')
  })
})
