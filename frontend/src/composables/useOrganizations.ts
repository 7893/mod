import { computed, onScopeDispose, ref, watch, type MaybeRefOrGetter, toValue } from 'vue'
import { requestJson } from '../api/http.ts'
import type { EntityRow } from '../stores/project.ts'

export interface FetchEntitiesParams {
  page?: number
  pageSize?: number
  region?: string
  status?: string
  batch?: number
  keyword?: string
}

interface PageResponse {
  items: EntityRow[]
  total: number
  page: number
  page_size: number
}

export function useOrganizations(params: {
  pageSize?: MaybeRefOrGetter<number>
  region?: MaybeRefOrGetter<string | null>
  status?: MaybeRefOrGetter<string | null>
  batch?: MaybeRefOrGetter<string | null>
  keyword?: MaybeRefOrGetter<string>
} = {}) {
  const page = ref(1)
  const items = ref<EntityRow[]>([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref<Error | null>(null)
  let activeRequest: AbortController | null = null
  let requestSequence = 0
  
  const pageSize = computed(() => toValue(params.pageSize) ?? 20)
  const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
  
  async function fetchPage(p: number = page.value) {
    activeRequest?.abort()
    const request = new AbortController()
    activeRequest = request
    const sequence = ++requestSequence
    loading.value = true
    error.value = null
    
    const queryParams = new URLSearchParams()
    queryParams.set('page', String(p))
    queryParams.set('page_size', String(pageSize.value))
    
    const region = toValue(params.region)
    if (region && region !== '全部' && region !== '全部省份') {
      queryParams.set('region', region)
    }
    
    const status = toValue(params.status)
    if (status && status !== '全部' && status !== '全部状态') {
      queryParams.set('status', status)
    }
    
    const batch = toValue(params.batch)
    if (batch && batch !== '全部' && batch !== '全部批次') {
      // 从 "第N批" 提取数字
      const m = batch.match(/第(\d+)批/)
      if (m) {
        queryParams.set('batch', m[1])
      }
    }
    
    const keyword = toValue(params.keyword)
    if (keyword) {
      queryParams.set('keyword', keyword)
    }
    
    try {
      const data = await requestJson<PageResponse>(`organizations?${queryParams}`, {
        signal: request.signal,
      })
      if (sequence !== requestSequence) return
      items.value = data.items
      total.value = data.total
      page.value = data.page
    } catch (e) {
      if (request.signal.aborted || sequence !== requestSequence) return
      error.value = e instanceof Error ? e : new Error(String(e))
      console.error('[useOrganizations] fetch failed:', e)
    } finally {
      if (sequence === requestSequence) loading.value = false
    }
  }
  
  // 监听筛选条件变化，重置到第1页并刷新
  watch(
    [
      () => toValue(params.region),
      () => toValue(params.status),
      () => toValue(params.batch),
      () => toValue(params.keyword),
    ],
    () => {
      page.value = 1
      fetchPage(1)
    },
    { immediate: true }
  )

  onScopeDispose(() => activeRequest?.abort())
  
  // 翻页
  function goToPage(p: number) {
    if (p >= 1 && p <= totalPages.value && p !== page.value) {
      page.value = p
      fetchPage(p)
    }
  }
  
  function refresh() {
    return fetchPage(page.value)
  }
  
  return {
    items,
    total,
    page,
    totalPages,
    pageSize,
    loading,
    error,
    goToPage,
    refresh,
  }
}
