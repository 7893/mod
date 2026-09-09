import { computed, ref, watch, type ComputedRef, type Ref, type WatchSource } from 'vue'

export interface PagedList<T> {
  page: Ref<number>
  pageSize: Ref<number>
  totalPages: ComputedRef<number>
  total: ComputedRef<number>
  items: ComputedRef<T[]>
}

/**
 * 客户端分页骨架：切片、总页数、筛选变动回到第 1 页、总页数收缩时安全钳位。
 * 所有台账/清单必须复用，不得在组件内重写分页状态机。
 */
export function usePagedList<T>(
  source: () => T[],
  options: { pageSize: number; resetOn?: WatchSource[] },
): PagedList<T> {
  const page = ref(1)
  const pageSize = ref(options.pageSize)
  const total = computed(() => source().length)
  const totalPages = computed(() => Math.ceil(total.value / pageSize.value) || 1)

  if (options.resetOn?.length) {
    watch(options.resetOn, () => {
      page.value = 1
    })
  }

  watch(totalPages, (next) => {
    if (page.value > next) page.value = Math.max(1, next)
  })

  const items = computed(() => {
    const safePage = Math.min(Math.max(1, page.value), totalPages.value)
    const start = (safePage - 1) * pageSize.value
    return source().slice(start, start + pageSize.value)
  })

  return { page, pageSize, totalPages, total, items }
}
