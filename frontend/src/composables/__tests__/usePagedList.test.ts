import { describe, it, expect } from 'vitest'
import { nextTick, ref } from 'vue'
import { usePagedList } from '../usePagedList'

const rows = (n: number) => Array.from({ length: n }, (_, i) => i + 1)

describe('usePagedList', () => {
  it('slices the source by page and reports total pages', () => {
    const source = ref(rows(23))
    const paged = usePagedList(() => source.value, { pageSize: 10 })
    expect(paged.totalPages.value).toBe(3)
    expect(paged.items.value).toEqual(rows(10))
    paged.page.value = 3
    expect(paged.items.value).toEqual([21, 22, 23])
  })

  it('reports one page for an empty source', () => {
    const paged = usePagedList(() => [], { pageSize: 10 })
    expect(paged.totalPages.value).toBe(1)
    expect(paged.items.value).toEqual([])
  })

  it('resets to page 1 when a filter source changes', async () => {
    const source = ref(rows(50))
    const filter = ref('')
    const paged = usePagedList(() => source.value, { pageSize: 10, resetOn: [filter] })
    paged.page.value = 4
    filter.value = 'x'
    await nextTick()
    expect(paged.page.value).toBe(1)
  })

  it('clamps the page to at least 1 when the source shrinks to empty', async () => {
    const source = ref(rows(50))
    const paged = usePagedList(() => source.value, { pageSize: 10 })
    paged.page.value = 5
    source.value = []
    await nextTick()
    expect(paged.page.value).toBe(1)
    source.value = rows(15)
    await nextTick()
    expect(paged.items.value).toEqual(rows(10))
  })
})
