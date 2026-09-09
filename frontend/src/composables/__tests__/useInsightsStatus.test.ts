import { describe, it, expect, afterEach, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { useInsightsStatus } from '../useInsightsStatus'

function runInSetup<T>(fn: () => T): { result: T; unmount: () => void } {
  let result!: T
  const wrapper = mount(defineComponent({
    setup() {
      result = fn()
      return () => h('div')
    },
  }))
  return { result, unmount: () => wrapper.unmount() }
}

describe('useInsightsStatus', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('loads status on mount, polls every minute and stops on unmount', async () => {
    vi.useFakeTimers()
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ hw_ml: { status: 'ready' }, predictions: [{ orgId: 1 }] }),
    })
    globalThis.fetch = fetchMock

    const { result, unmount } = runInSetup(() => useInsightsStatus())
    await flushPromises()
    expect(result.status.value?.hw_ml?.status).toBe('ready')
    expect(result.status.value?.predictions).toHaveLength(1)
    expect(fetchMock).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(60_000)
    expect(fetchMock).toHaveBeenCalledTimes(2)

    unmount()
    await vi.advanceTimersByTimeAsync(120_000)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('keeps the last good status and records the error on failure', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 503, json: async () => ({}) })
    const { result, unmount } = runInSetup(() => useInsightsStatus())
    await flushPromises()
    expect(result.status.value).toBeNull()
    expect(result.error.value).toBe('HTTP 503')
    unmount()
  })
})
