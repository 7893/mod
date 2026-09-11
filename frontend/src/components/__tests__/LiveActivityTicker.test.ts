import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import LiveActivityTicker from '../LiveActivityTicker.vue'

describe('LiveActivityTicker', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders an honest empty state instead of fabricated activities when fetch is empty', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([]),
      }),
    )

    const wrapper = mount(LiveActivityTicker)
    await flushPromises()

    expect(wrapper.text()).toContain('治理自愈动态广播')
    expect(wrapper.text()).toContain('暂无治理活动记录')
    expect(wrapper.findAll('button').length).toBe(0)
  })

  it('renders live activities returned from api and advances on next button click', async () => {
    const mockActivities = [
      {
        id: 1,
        issueId: 'ISS-001',
        action: '闭环销项',
        actor: '数字化总指挥部',
        detail: '分录试算完全平衡。',
        timeStr: '11:22:33',
        occurredAt: '2026-09-08 11:22:33',
        unitName: '神华测试公司',
        province: '内蒙古',
        issueType: '票据异常',
        status: 'RESOLVED',
      },
      {
        id: 2,
        issueId: 'ISS-002',
        action: '现场排查',
        actor: '平账专项组',
        detail: '排查历史总账科目。',
        timeStr: '11:25:00',
        occurredAt: '2026-09-08 11:25:00',
        unitName: '大同煤业分公司',
        province: '山西',
        issueType: '超期挂账',
        status: 'IN_PROGRESS',
      },
    ]

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockActivities),
      }),
    )

    const wrapper = mount(LiveActivityTicker)
    await flushPromises()

    expect(wrapper.text()).toContain('神华测试公司')
    expect(wrapper.text()).toContain('11:22:33')

    // Click next button
    const buttons = wrapper.findAll('button')
    expect(buttons.length).toBe(2)
    await buttons[1].trigger('click')

    expect(wrapper.text()).toContain('大同煤业分公司')
    expect(wrapper.text()).toContain('11:25:00')
  })

  it('clears old stories on an empty poll and cancels polling on unmount', async () => {
    vi.useFakeTimers()
    const event = { id: 1, issueId: 'I1', unitName: '旧事件单位', detail: '旧事件', occurredAt: '2026-09-11 10:00:00' }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [event] })
      .mockResolvedValue({ ok: true, json: async () => [] })
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mount(LiveActivityTicker)
    await flushPromises()
    expect(wrapper.text()).toContain('旧事件单位')
    await vi.advanceTimersByTimeAsync(30000)
    expect(wrapper.text()).not.toContain('旧事件单位')
    expect(wrapper.emitted('activities')?.at(-1)).toEqual([[]])
    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(30000)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    vi.useRealTimers()
  })
})
