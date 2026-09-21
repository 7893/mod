import { computed, toValue, type MaybeRefOrGetter, type WatchSource } from 'vue'
import { useProjectStore, type EntityRow } from '../stores/project.ts'
import { ALL, matchesEntityQuery, matchesOption } from '../utils/entityOptions.ts'
import { usePagedList } from './usePagedList.ts'

interface EntityLedgerOptions {
  pageSize: number
  province?: MaybeRefOrGetter<string | null | undefined>
  batch?: MaybeRefOrGetter<string | null | undefined>
  status?: MaybeRefOrGetter<string | null | undefined>
  readiness?: MaybeRefOrGetter<string | null | undefined>
  query?: MaybeRefOrGetter<string | null | undefined>
}

function selected(value: MaybeRefOrGetter<string | null | undefined> | undefined): string {
  return value === undefined ? ALL : (toValue(value) || ALL)
}

/**
 * 单位类台账唯一读取内核。
 *
 * 数据只来自全局快照的 store.entities；各业务台账只能配置筛选维度和每页行数，
 * 不得再为同一批单位另起网络请求或重算后端五表投影。
 */
export function useEntityLedger(options: EntityLedgerOptions) {
  const store = useProjectStore()
  const filtered = computed<EntityRow[]>(() => store.entities.filter((row) => (
    matchesOption(selected(options.province), row.province)
    && matchesOption(selected(options.batch), row.batch)
    && matchesOption(selected(options.status), row.status)
    && matchesOption(selected(options.readiness), row.readinessStatus)
    && matchesEntityQuery(row, toValue(options.query) || '')
  )))

  const resetOn: WatchSource[] = [
    () => selected(options.province),
    () => selected(options.batch),
    () => selected(options.status),
    () => selected(options.readiness),
    () => toValue(options.query) || '',
  ]
  const pagination = usePagedList(() => filtered.value, {
    pageSize: options.pageSize,
    resetOn,
  })

  return {
    all: computed(() => store.entities),
    filtered,
    ...pagination,
  }
}
