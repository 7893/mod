import { formatDateTime } from '../formatters/metrics.ts'
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import snapshotData from '../data/fallback-snapshot.json'

/** 展示四态，与后端 business_rules.DISPLAY_STATUSES 一致：DB 六态由后端折叠，「已上线」含「稳定运行」。 */
export type RolloutStatus = '未启动' | '准备中' | '双轨运行' | '已上线'

export interface EntityRow {
  id: number
  province: string
  region?: string
  name: string
  batch: string
  batchId?: number
  owner: string
  rawOwner?: string
  status: RolloutStatus
  construction: number
  openingData: number
  readinessStatus?: '已导入' | '已校验' | '收集中' | '未收集' | null
  voucherRate: number | null
  updatedAt: string
}

export interface AuditRow {
  id: number
  time: string
  operator: string
  entity: string
  field: string
  before: string
  after: string
}

export interface RolloutBatchItem {
  batchId: number
  name: string
  total: number
  launched: number
  dual: number
  launchedPct: number
  constructionPct: number
  stageLabel?: string
}

export interface TrendItem {
  date: string
  fullDate?: string
  launched: number
  dual?: number
}

export interface RolloutTrendItem {
  date: string
  fullDate: string
  batchId: number
  name: string
  total: number
  launchedPct: number
  dualPct: number
}

export interface OperationsTrendItem {
  date: string
  fullDate: string
  documents: number | null
  vouchers: number | null
  integrations: number | null
  integrationSuccessPct: number | null
}

export interface ProvinceItem {
  name: string
  region: string
  regionDisplay: string
  value: number
  total: number
  launched: number
  dual: number
  constructionPct: number
  todayAdded?: number
  docsTodayAdded?: number
  docsAddedAsOfDate?: string
  vouchersTodayAdded?: number
  vouchersAddedAsOfDate?: string
}

export interface IssueItem {
  type: string
  level: string
  title: string
  area: string
  owner: string
  due: string
  status: string
  leadershipAttention: boolean
  orgName: string
}

export interface IssuesSummary {
  latestDate: string
  totalUnresolved: number
  totalResolved: number
  totalIssues: number
  closeRate: number
  highRisk: number
  mediumRisk: number
  lowRisk: number
  byStage: Array<{
    stage: string
    bug: number
    req: number
    conf: number
    data: number
    integ: number
    op: number
    total: number
    resolved: number
    unresolved: number
  }>
  byBatch: Array<{
    batchId: number
    name: string
    unresolved: number
    high: number
    medium: number
    low: number
  }>
}

export interface TaskStageItem {
  name: string
  total: number
  completed: number
  inProgress: number
  notStarted: number
  avgProgress: number
}

export interface ConstructionData {
  totalTasks: number
  completedTasks: number
  inProgressTasks: number
  notStartedTasks: number
  avgProgress: number
  taskStages: TaskStageItem[]
  trainingSummary: {
    totalSessions: number
    totalExpected: number
    totalActual: number
    totalPassed: number
    totalCert: number
    byType: Array<{
      type: string
      count: number
      expected: number
      actual: number
      passed: number
      cert: number
    }>
  }
  dataReadinessSummary: {
    total: number
    imported: number
    verified: number
    collecting: number
    notCollected: number
  }
}

/** 快照内的 insights 只承载规则告警；模型/预测状态由 /api/insights/status 单独提供。 */
export interface InsightsData {
  ruleBasedAlerts: Array<{
    level: string
    title: string
    detail: string
  }>
}

export interface ProjectSnapshot {
  businessRules: {
    lifecycle: {
      dualRunConsistencyRateMin: number
      /** DB 六态（有序）。 */
      orgStages: string[]
      /** 计入「已上线」口径的 DB 状态。 */
      launchedStatuses: string[]
      /** 前端展示四态（有序）。 */
      displayStatuses: RolloutStatus[]
    }
    risk: {
      constructionLagRate: number
      /** 建设滞后中再低于此线为「高危」。 */
      constructionCriticalRate: number
      openingDataLagRate: number
      lastActiveBatchId: number
    }
  }
  meta: {
    mode: string
    notice: string
    seed: number
    fullRows: number
    sampleRows: number
    period: [string, string]
    asOfDate: string
    sourceTimezone: string
    displayTimezone: string
    generatedAt?: string
    /** 后端如实标注：live 为真库快照，fallback 为内置兜底；缺省（旧版后端）按 live 处理。 */
    source?: 'live' | 'fallback' | 'none'
  }
  overview: {
    orgTotal: number
    orgTodayAdded: number
    orgAddedAsOfDate?: string
    orgAddedNote?: string
    contactsTotal: number
    contactsCoveredOrgs: number
    contactsCoveragePct: number
    contactsTodayAdded: number
    contactsAddedAsOfDate?: string
    contactsAddedNote?: string
    docsTotal: number
    docsTodayAdded: number
    docsAddedAsOfDate?: string
    vouchersTotal: number
    vouchersTodayAdded: number
    vouchersAddedAsOfDate?: string
    asOfDate: string
    launched: number
    launchedPct: number
    dual: number
    constructionPct: number
    voucherTotal: number
    voucherSuccessPct: number
    integrationSuccessPct: number
    unresolvedIssues: number
    highRisk: number
    issuesSummaryText?: string
    batches?: number
    regions: number
  }
  rollout: RolloutBatchItem[]
  trend: TrendItem[]
  rolloutTrend?: RolloutTrendItem[]
  provinces: ProvinceItem[]
  entities: EntityRow[]
  issues: IssueItem[]
  issuesSummary: IssuesSummary
  operations: {
    businessDocument: number
    businessDocumentLine: number
    accountingVoucher: number
    accountingVoucherLine: number
    documentVoucherLink: number
    integrationResult: number
    integrationSuccess?: number
    integrationFailed?: number
    dualRunResult: number
    dualRunConsistent?: number
    dualRunInconsistent?: number
    dualRunConsistencyPct?: number
    dualRunBreakdown?: Array<{
      type: string
      consistent: number
      inconsistent: number
      total: number
      rate: number
    }>
  }
  operationsTrend?: OperationsTrendItem[]
  quality?: {
    voucherBalanceErrors?: number | null
    timeOrderErrors?: number | null
    orphanLinkErrors?: number | null
    organizationsWithStatusProgression?: number | null
  } | null
  construction: ConstructionData
  insights: InsightsData
}

const FALLBACK_BUSINESS_RULES: ProjectSnapshot['businessRules'] = {
  lifecycle: {
    dualRunConsistencyRateMin: 98,
    orgStages: ['未启动', '准备中', '已具备双轨条件', '双轨运行中', '已上线', '稳定运行'],
    launchedStatuses: ['已上线', '稳定运行'],
    displayStatuses: ['未启动', '准备中', '双轨运行', '已上线'],
  },
  risk: { constructionLagRate: 88, constructionCriticalRate: 80, openingDataLagRate: 88, lastActiveBatchId: 7 },
}

const initialSnapshot = {
  ...(snapshotData as unknown as ProjectSnapshot),
  businessRules: FALLBACK_BUSINESS_RULES,
}
const seeds = initialSnapshot.entities as EntityRow[]

export const useProjectStore = defineStore('project', () => {
  const snapshot = ref<ProjectSnapshot>(initialSnapshot)
  const entities = ref<EntityRow[]>([...seeds])
  const loading = ref(false)
  const connectionError = ref('')
  const lastLoadedAt = ref<Date | null>(null)
  const dataSource = ref<'fallback' | 'live'>('fallback')
  const pollIntervalMs = ref(60000) // Default 60s
  let timerId: number | null = null
  let refreshSequence = 0

  const audits = ref<AuditRow[]>([
    { id: 1, time: '2026-08-30 15:10:08', operator: '项目管理员', entity: '第一批·羊城林业研究院', field: '上线状态', before: '双轨运行', after: '已上线' },
    { id: 2, time: '2026-08-30 14:51:32', operator: '数据负责人', entity: '第二批·辽宁生态发展中心', field: '期初数据完成率', before: '98%', after: '100%' },
  ])

  const statusCount = computed(() => entities.value.reduce<Record<string, number>>((acc, row) => {
    acc[row.status] = (acc[row.status] ?? 0) + 1
    return acc
  }, {}))

  const provinceSummary = computed<ProvinceItem[]>(() => {
    if (snapshot.value.provinces && snapshot.value.provinces.length > 0) {
      return snapshot.value.provinces
    }
    const grouped = new Map<string, { total: number; launched: number; dual: number; score: number }>()
    entities.value.forEach((row) => {
      const current = grouped.get(row.province) ?? { total: 0, launched: 0, dual: 0, score: 0 }
      current.total += 1
      current.launched += row.status === '已上线' ? 1 : 0
      current.dual += row.status === '双轨运行' ? 1 : 0
      current.score += row.construction
      grouped.set(row.province, current)
    })
    const NATIONAL_PROVINCE_ORDER = [
      '北京', '天津', '河北', '山西', '内蒙古',
      '辽宁', '吉林', '黑龙江',
      '上海', '江苏', '浙江', '安徽', '福建', '江西', '山东',
      '河南', '湖北', '湖南', '广东', '广西', '海南',
      '重庆', '四川', '贵州', '云南', '西藏',
      '陕西', '甘肃', '青海', '宁夏', '新疆',
      '香港', '澳门', '台湾',
    ]
    const list = [...grouped].map(([name, v]) => ({
      name,
      region: name,
      regionDisplay: name,
      value: Math.round(v.score / v.total),
      constructionPct: Math.round(v.score / v.total),
      total: v.total,
      launched: v.launched,
      dual: v.dual,
      todayAdded: 0,
      docsTodayAdded: 0,
      docsAddedAsOfDate: '2026-08-29',
      vouchersTodayAdded: 0,
      vouchersAddedAsOfDate: '2026-08-30',
    }))
    list.sort((a, b) => {
      const ia = NATIONAL_PROVINCE_ORDER.indexOf(a.name)
      const ib = NATIONAL_PROVINCE_ORDER.indexOf(b.name)
      return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib)
    })
    return list
  })

  function updateEntity(id: number, patch: Partial<EntityRow>) {
    const row = entities.value.find((item) => item.id === id)
    if (!row) return
    const labels: Record<string, string> = {
      status: '上线状态',
      construction: '建设完成率',
      openingData: '期初数据完成率',
      owner: '项目联系人',
    }
    Object.entries(patch).forEach(([field, after]) => {
      const before = String(row[field as keyof EntityRow] ?? '')
      if (before === String(after)) return
      audits.value.unshift({
        id: Date.now() + audits.value.length,
        time: formatDateTime(new Date(), { seconds: true }),
        operator: '项目管理员',
        entity: row.name,
        field: labels[field] ?? field,
        before: field.includes('construction') || field.includes('openingData') ? `${before}%` : before,
        after: field.includes('construction') || field.includes('openingData') ? `${after}%` : String(after),
      })
    })
    Object.assign(row, patch, { updatedAt: '刚刚' })
  }

  async function refresh(silent = false) {
    // KI-059：绝不整屏/顶栏转圈。首屏与轮询始终已有兜底或上一份有效快照可展示，
    // 因此只在“完全没有任何可展示数据”这种极端情况下才显示 loading。
    // 由于 store 初始即用内置兜底快照预填 entities，正常运行下 loading 永不被置真，
    // 后端快照冷启动（即使 >1s）也只是静默替换数据，用户看不到转圈。
    const requestSequence = ++refreshSequence
    const hasDisplayableData = entities.value.length > 0
    const showLoading = !silent && !hasDisplayableData
    if (showLoading) loading.value = true
    try {
      const response = await fetch(`${import.meta.env.BASE_URL}api/dashboard/snapshot`, {
        cache: 'no-store',
      })
      if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      const raw = await response.json()
      // KI-075: 后端快照契约已全量 camelCase（后端有 camelCase 契约测试保障），前端不再做键名转换。
      const live = raw as ProjectSnapshot
      if (requestSequence !== refreshSequence) return
      live.businessRules = live.businessRules || FALLBACK_BUSINESS_RULES
      snapshot.value = live
      if (Array.isArray(live.entities)) {
        entities.value = live.entities
      }
      lastLoadedAt.value = new Date()
      dataSource.value = live.meta?.source === 'fallback' || live.meta?.source === 'none' ? 'fallback' : 'live'
      connectionError.value = ''
    } catch (error) {
      if (requestSequence !== refreshSequence) return
      const msg = error instanceof Error ? error.message : '网络连接异常'
      connectionError.value = `数据刷新受阻（${msg}），当前维持上一有效快照`
    } finally {
      if (requestSequence === refreshSequence && showLoading) loading.value = false
    }
  }

  function startPolling() {
    stopPolling()
    timerId = window.setInterval(() => {
      void refresh(true)
    }, pollIntervalMs.value)
  }

  function stopPolling() {
    if (timerId !== null) {
      window.clearInterval(timerId)
      timerId = null
    }
  }

  // Initial load & start polling
  void refresh()
  startPolling()

  // Vite HMR 会重新执行 store 模块；旧模块必须主动释放轮询，避免开发环境重复请求。
  import.meta.hot?.dispose(stopPolling)

  return {
    snapshot,
    entities,
    audits,
    statusCount,
    provinceSummary,
    loading,
    connectionError,
    lastLoadedAt,
    dataSource,
    pollIntervalMs,
    refresh,
    updateEntity,
    startPolling,
    stopPolling,
  }
})
