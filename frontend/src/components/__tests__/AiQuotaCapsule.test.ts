import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import AiQuotaCapsule from '../AiQuotaCapsule.vue'

describe('AiQuotaCapsule', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders project quota without claiming an account billing guarantee', async () => {
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

    expect(wrapper.text()).toContain('治理 AI')
    expect(wrapper.text()).toContain('12.5')
    expect(wrapper.text()).toContain('3000')
    expect(wrapper.text()).toContain('预算正常')
    expect(wrapper.text()).not.toContain('$0.00')
    expect(wrapper.attributes('title')).toContain('不代表 Cloudflare 账户账单')
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
