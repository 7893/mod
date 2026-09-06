import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { useAiInsights } from '../useAiInsights'

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

describe('useAiInsights', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('initializes and polls status on mount', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'unavailable' }),
    })
    globalThis.fetch = fetchMock

    const { result, unmount } = runInSetup(() => useAiInsights())

    // Initial state before fetch resolves
    expect(result.aiPhase.value).toBe('loading')

    await flushPromises()
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/insights/status'))
    expect(result.aiPhase.value).toBe('unavailable')
    expect(result.aiStatus.value).toEqual({ status: 'unavailable' })
    unmount()
  })

  it('transitions to ok and cache_hit through fetchLatest when status is ok', async () => {
    const fetchMock = vi.fn().mockImplementation(async (url: string) => {
      if (url.includes('/insights/status')) {
        return {
          ok: true,
          json: async () => ({ status: 'ok', quota_remaining: 85 }),
        }
      }
      if (url.includes('/insights/latest')) {
        return {
          ok: true,
          json: async () => ({
            status: 'ok',
            content: '测试研判内容',
            cache_hit: true,
            generated_at: '2026-09-06T10:00:00Z',
            quota_remaining: 85,
          }),
        }
      }
      throw new Error(`Unhandled url: ${url}`)
    })
    globalThis.fetch = fetchMock

    const { result, unmount } = runInSetup(() => useAiInsights())
    await flushPromises()

    expect(result.aiPhase.value).toBe('cache_hit')
    expect(result.aiLatest.value?.content).toBe('测试研判内容')
    expect(result.aiButtonLabel.value).toBe('重新生成')
    expect(result.aiButtonDisabled.value).toBe(false)
    expect(result.quotaRemaining.value).toBe(85)
    expect(result.generatedAt.value).not.toBeNull()
    unmount()
  })

  it('handles rate_limited status properly', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'rate_limited', message: 'Rate limit exceeded' }),
    })
    globalThis.fetch = fetchMock

    const { result, unmount } = runInSetup(() => useAiInsights())
    await flushPromises()

    expect(result.aiPhase.value).toBe('rate_limited')
    expect(result.aiButtonDisabled.value).toBe(true)
    unmount()
  })

  it('handles network error in fetchStatus and gracefully degrades', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error('Network offline'))
    globalThis.fetch = fetchMock

    const { result, unmount } = runInSetup(() => useAiInsights())
    await flushPromises()

    expect(result.aiPhase.value).toBe('unavailable')
    expect(result.aiError.value).toBe('Network offline')
    expect(result.aiButtonDisabled.value).toBe(true)
    unmount()
  })

  it('executes triggerGenerate successfully', async () => {
    const fetchMock = vi.fn().mockImplementation(async (url: string, options?: any) => {
      if (options?.method === 'POST') {
        return {
          ok: true,
          json: async () => ({
            status: 'ok',
            content: '新生成的研判分析报告',
            cache_hit: false,
            generated_at: '2026-09-06T12:00:00Z',
          }),
        }
      }
      return {
        ok: true,
        json: async () => ({ status: 'no_cache' }),
      }
    })
    globalThis.fetch = fetchMock

    const { result, unmount } = runInSetup(() => useAiInsights())
    await flushPromises()
    expect(result.aiPhase.value).toBe('no_cache')

    // Trigger generate
    const genPromise = result.triggerGenerate()
    expect(result.aiGenerating.value).toBe(true)
    expect(result.aiPhase.value).toBe('generating')
    expect(result.aiButtonLabel.value).toBe('生成中…')

    await genPromise
    expect(result.aiGenerating.value).toBe(false)
    expect(result.aiPhase.value).toBe('ok')
    expect(result.aiLatest.value?.content).toBe('新生成的研判分析报告')
    unmount()
  })

  it('handles 429 rate limit on triggerGenerate', async () => {
    const fetchMock = vi.fn().mockImplementation(async (url: string, options?: any) => {
      if (options?.method === 'POST') {
        return {
          ok: false,
          status: 429,
          json: async () => ({ status: 'rate_limited', message: 'Too many requests' }),
        }
      }
      return {
        ok: true,
        json: async () => ({ status: 'no_cache' }),
      }
    })
    globalThis.fetch = fetchMock

    const { result, unmount } = runInSetup(() => useAiInsights())
    await flushPromises()

    await result.triggerGenerate()
    expect(result.aiGenerating.value).toBe(false)
    expect(result.aiPhase.value).toBe('rate_limited')
    unmount()
  })

  it('prevents concurrent triggerGenerate when already generating', async () => {
    let resolvePost!: (val: any) => void
    const postPromise = new Promise((resolve) => {
      resolvePost = resolve
    })

    const fetchMock = vi.fn().mockImplementation(async (url: string, options?: any) => {
      if (options?.method === 'POST') {
        return postPromise
      }
      return {
        ok: true,
        json: async () => ({ status: 'no_cache' }),
      }
    })
    globalThis.fetch = fetchMock

    const { result, unmount } = runInSetup(() => useAiInsights())
    await flushPromises()

    const p1 = result.triggerGenerate()
    expect(result.aiGenerating.value).toBe(true)

    // Second call should immediately return without new fetch
    const postCallsBefore = fetchMock.mock.calls.filter((c) => c[1]?.method === 'POST').length
    await result.triggerGenerate()
    const postCallsAfter = fetchMock.mock.calls.filter((c) => c[1]?.method === 'POST').length
    expect(postCallsAfter).toBe(postCallsBefore)

    // Complete p1
    resolvePost({
      ok: true,
      json: async () => ({ status: 'ok', content: 'done' }),
    })
    await p1
    unmount()
  })
})
