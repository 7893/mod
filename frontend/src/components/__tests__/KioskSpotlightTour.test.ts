import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import KioskSpotlightTour from '../KioskSpotlightTour.vue'

describe('KioskSpotlightTour', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('remains hidden when idle time has not reached threshold', () => {
    const wrapper = mount(KioskSpotlightTour, {
      props: { idleTimeoutMs: 1000 },
    })

    expect(wrapper.find('.fixed').exists()).toBe(false)
  })

  it('activates and displays spotlight card when idle timeout expires', async () => {
    const wrapper = mount(KioskSpotlightTour, {
      props: { idleTimeoutMs: 1000 },
    })

    vi.advanceTimersByTime(1100)
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.fixed').exists()).toBe(true)
    expect(wrapper.text()).toContain('展厅巡航模式 · 治理攻坚聚光灯')
    expect(wrapper.text()).toContain('北方特种装备工业集团')
  })

  it('hides when user activity occurs', async () => {
    const wrapper = mount(KioskSpotlightTour, {
      props: { idleTimeoutMs: 1000 },
    })

    vi.advanceTimersByTime(1100)
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.fixed').exists()).toBe(true)

    // Trigger mouse move on window
    window.dispatchEvent(new Event('mousemove'))
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.fixed').exists()).toBe(false)
  })
})
