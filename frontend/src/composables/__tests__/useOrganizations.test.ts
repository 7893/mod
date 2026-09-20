import { effectScope, nextTick, ref } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useOrganizations } from '../useOrganizations'
import type { EntityRow } from '../../stores/project'

interface PendingRequest {
  url: string
  signal: AbortSignal
  resolve: (value: unknown) => void
  reject: (reason: unknown) => void
}

describe('useOrganizations', () => {
  afterEach(() => vi.restoreAllMocks())

  it('cancels an obsolete filter request and keeps the latest response', async () => {
    const pending: PendingRequest[] = []
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => new Promise((resolve, reject) => {
      const signal = init?.signal as AbortSignal
      pending.push({ url, signal, resolve, reject })
      signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
    })))

    const region = ref('北京')
    const scope = effectScope()
    const organizations = scope.run(() => useOrganizations({ region }))!
    await nextTick()

    region.value = '上海'
    await nextTick()

    expect(pending).toHaveLength(2)
    expect(pending[0]?.signal.aborted).toBe(true)
    expect(pending[1]?.url).toContain('region=%E4%B8%8A%E6%B5%B7')

    const latest = [{ id: 2, name: '上海单位' }] as EntityRow[]
    pending[1]?.resolve({
      ok: true,
      json: async () => ({ items: latest, total: 1, page: 1, page_size: 20 }),
    })
    await flushPromises()

    expect(organizations.items.value).toEqual(latest)
    scope.stop()
  })
})
