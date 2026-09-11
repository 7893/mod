import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import KioskSpotlightTour from '../KioskSpotlightTour.vue'

const activities = [{ id: 1, issueId: 'ISS-TEST', action: '现场排查', actor: '测试专班', detail: '来自事件源的排查记录', timeStr: '10:00:00', occurredAt: '2026-09-11 10:00:00', unitName: '测试单位', province: '北京', issueType: '票据异常', status: 'IN_PROGRESS' }]

describe('KioskSpotlightTour', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('remains hidden when idle time has not reached threshold', () => {
    const wrapper = mount(KioskSpotlightTour, {
      props: { idleTimeoutMs: 1000, activities },
    })

    expect(wrapper.find('.fixed').exists()).toBe(false)
  })

  it('activates and displays spotlight card when idle timeout expires', async () => {
    const wrapper = mount(KioskSpotlightTour, {
      props: { idleTimeoutMs: 1000, activities },
    })

    vi.advanceTimersByTime(1100)
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.fixed').exists()).toBe(true)
    expect(wrapper.text()).toContain('展厅巡航模式 · 治理攻坚聚光灯')
    expect(wrapper.text()).toContain('来自事件源的排查记录')
    await wrapper.findAll('button').at(-1)!.trigger('click')
    expect(wrapper.emitted('inspect')).toEqual([['ISS-TEST']])
  })

  it('hides when user activity occurs', async () => {
    const wrapper = mount(KioskSpotlightTour, {
      props: { idleTimeoutMs: 1000, activities },
    })

    vi.advanceTimersByTime(1100)
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.fixed').exists()).toBe(true)

    // Trigger mouse move on window
    window.dispatchEvent(new Event('mousemove'))
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.fixed').exists()).toBe(false)
  })

  it('does not invent stories when events disappear or a drawer is open', async () => {
    const wrapper = mount(KioskSpotlightTour, { props: { idleTimeoutMs: 1000, activities } })
    await vi.advanceTimersByTimeAsync(1100)
    expect(wrapper.find('.fixed').exists()).toBe(true)
    await wrapper.setProps({ suspended: true })
    expect(wrapper.find('.fixed').exists()).toBe(false)
    await wrapper.setProps({ suspended: false, activities: [] })
    expect(wrapper.find('.fixed').exists()).toBe(false)
  })
})
