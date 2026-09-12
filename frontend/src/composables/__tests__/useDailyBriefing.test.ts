import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { useDailyBriefing } from '../useDailyBriefing'

function runInSetup<T>(fn: () => T): { result: T; unmount: () => void } {
  let result!: T
  const comp = defineComponent({
    setup() {
      result = fn()
      return () => h('div')
    },
  })
  const wrapper = mount(comp)
  return { result, unmount: () => wrapper.unmount() }
}

describe('useDailyBriefing', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('fetches briefing automatically on mount and succeeds', async () => {
    const mockData = {
      status: 'ok',
      briefingDate: '2026-09-06',
      content: '今日推广工作稳步推进，第七批单位进入双轨准备阶段。',
      model: '@cf/meta/llama-3.1-8b-instruct',
      generatedAt: '2026-09-06T00:30:00+08:00',
    }

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockData,
    })
    globalThis.fetch = fetchMock

    const { result, unmount } = runInSetup(() => useDailyBriefing())
    expect(result.loading.value).toBe(true)

    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/insights/briefing'))
    expect(result.loading.value).toBe(false)
    expect(result.briefing.value).toEqual(mockData)
    unmount()
  })

  it('gracefully degrades to no_briefing on network/fetch failure', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error('Connection refused'))
    globalThis.fetch = fetchMock

    const { result, unmount } = runInSetup(() => useDailyBriefing())
    await flushPromises()

    expect(result.loading.value).toBe(false)
    expect(result.briefing.value).toEqual({ status: 'no_briefing' })
    unmount()
  })

  it('supports manual refetch through fetchBriefing', async () => {
    const initialData = { status: 'no_briefing' }
    const updatedData = {
      status: 'ok',
      briefingDate: '2026-09-06',
      content: '最新决策简报已生成。',
    }

    let count = 0
    const fetchMock = vi.fn().mockImplementation(async () => ({
      ok: true,
      json: async () => (count++ === 0 ? initialData : updatedData),
    }))
    globalThis.fetch = fetchMock

    const { result, unmount } = runInSetup(() => useDailyBriefing())
    await flushPromises()
    expect(result.briefing.value?.status).toBe('no_briefing')

    // Refetch
    await result.fetchBriefing()
    expect(result.briefing.value?.status).toBe('ok')
    expect(result.briefing.value?.content).toBe('最新决策简报已生成。')
    unmount()
  })
})

it('polls stale briefings and clears its timer on unmount', async () => {
  vi.useFakeTimers()
  try {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: true,
      json: async () => ({ status: 'ok', isStale: true, briefingDate: '2026-09-01' }) })
    const { result, unmount } = runInSetup(() => useDailyBriefing())
    await vi.advanceTimersByTimeAsync(0)
    expect(result.briefing.value?.isStale).toBe(true)
    await vi.advanceTimersByTimeAsync(60_000)
    expect(globalThis.fetch).toHaveBeenCalledTimes(2)
    unmount()
    await vi.advanceTimersByTimeAsync(60_000)
    expect(globalThis.fetch).toHaveBeenCalledTimes(2)
  } finally { vi.useRealTimers() }
})

it('rejects HTTP errors even when their JSON body looks successful', async () => {
  globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 503,
    json: async () => ({ status: 'ok', content: 'wrong' }) })
  const { result, unmount } = runInSetup(() => useDailyBriefing())
  await flushPromises()
  expect(result.briefing.value?.status).toBe('no_briefing')
  unmount()
})
