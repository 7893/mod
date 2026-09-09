import type { AtRiskUnit, RiskAttribution } from '../components/AtRiskUnitTable.vue'
import type { ComplianceIssueUnit } from '../components/ComplianceInspectDrawer.vue'
import { formatPercent } from '../formatters/metrics.ts'
import type { EntityRow, ProjectSnapshot } from '../stores/project.ts'

export type BusinessRules = ProjectSnapshot['businessRules']

/**
 * 单位级风险判定，是 F 屏「困难户」与 E 屏「合规监督」的共同事实源。
 * 阈值一律来自后端 `businessRules`，此处不得出现数字字面量。
 */
export interface RiskFlags {
  dualInconsistent: boolean
  constructionLag: boolean
  openingDataLag: boolean
  prepStuck: boolean
}

const IN_PROGRESS_STATUSES = new Set<EntityRow['status']>(['建设中', '双轨运行'])

export function evaluateRiskFlags(row: EntityRow, rules: BusinessRules): RiskFlags {
  const inProgress = IN_PROGRESS_STATUSES.has(row.status)
  return {
    dualInconsistent:
      row.status === '双轨运行' &&
      row.voucherRate !== null &&
      row.voucherRate < rules.lifecycle.dualRunConsistencyRateMin,
    constructionLag: inProgress && row.construction < rules.risk.constructionLagRate,
    openingDataLag: inProgress && row.openingData < rules.risk.openingDataLagRate,
    prepStuck: row.status === '准备中' && row.batchId != null && row.batchId <= rules.risk.lastActiveBatchId,
  }
}

/** 预测侧补充特征（HeatWave AutoML 输出），按 orgId 索引。 */
export interface RiskPrediction {
  orgId: number | string
  stagnantDays?: number
  progressSlope14d?: number
  trainingErrorScissors?: number
  handlerConcentration?: number
  topAttributions?: RiskAttribution[]
}

export function indexPredictions(preds: unknown): Map<number, RiskPrediction> {
  const map = new Map<number, RiskPrediction>()
  if (!Array.isArray(preds)) return map
  for (const p of preds as RiskPrediction[]) {
    if (p && p.orgId != null) map.set(Number(p.orgId), p)
  }
  return map
}

function baseFields(row: EntityRow) {
  return {
    id: row.id,
    name: row.name,
    province: row.province,
    batch: row.batch,
    owner: row.owner,
    status: row.status,
    construction: row.construction,
    openingData: row.openingData,
    voucherRate: row.voucherRate,
  }
}

/** F 屏困难户清单：每个单位只归入最严重的一类风险。 */
export function deriveAtRiskUnits(
  rows: readonly EntityRow[],
  rules: BusinessRules,
  predictions: Map<number, RiskPrediction> = new Map(),
): AtRiskUnit[] {
  const list: AtRiskUnit[] = []
  for (const row of rows) {
    const flags = evaluateRiskFlags(row, rules)
    let risk: Pick<AtRiskUnit, 'riskType' | 'riskLevel' | 'reason'> | null = null
    if (flags.dualInconsistent) {
      risk = {
        riskType: '双轨核对差异',
        riskLevel: '高危',
        reason: `双轨入账凭证率仅 ${formatPercent(row.voucherRate)}，未达 ${rules.lifecycle.dualRunConsistencyRateMin}% 门禁，存在借贷试算不平风险`,
      }
    } else if (flags.constructionLag) {
      risk = {
        riskType: '建设严重滞后',
        riskLevel: row.construction < 80 ? '高危' : '重点关注',
        reason: `建设完成度 (${row.construction}%) 显著落后于批次推进均值，存在阶段脱轨掉队风险`,
      }
    } else if (flags.prepStuck) {
      risk = {
        riskType: '准备期卡顿',
        riskLevel: '重点关注',
        reason: '属于已推进批次但仍停留在准备中，期初数据收集或基础环境尚未打通',
      }
    }
    if (!risk) continue
    const pred = predictions.get(row.id)
    list.push({
      ...baseFields(row),
      ...risk,
      stagnantDays: pred?.stagnantDays,
      progressSlope14d: pred?.progressSlope14d,
      trainingErrorScissors: pred?.trainingErrorScissors,
      handlerConcentration: pred?.handlerConcentration,
    })
  }
  return list
}

export const COMPLIANCE_TAGS = ['超期挂账', '超预算迹象', '票据异常'] as const
export type ComplianceTag = (typeof COMPLIANCE_TAGS)[number]

/** E 屏合规监督清单：一个单位可同时带多个风险标签。 */
export function deriveComplianceUnits(rows: readonly EntityRow[], rules: BusinessRules): ComplianceIssueUnit[] {
  const result: ComplianceIssueUnit[] = []
  for (const row of rows) {
    const flags = evaluateRiskFlags(row, rules)
    if (!(flags.dualInconsistent || flags.constructionLag || flags.openingDataLag || flags.prepStuck)) continue

    const tags: string[] = []
    let detailNote = ''
    if (flags.openingDataLag) {
      tags.push('超期挂账')
      detailNote = `期初数据完成率仅 ${row.openingData}%，存在历史往来账目跨期未结清隐患。`
    }
    if (flags.constructionLag) {
      tags.push('超预算迹象')
      detailNote += `建设任务推进迟滞（${row.construction}%），多阶段工序返工引发预算预警。`
    }
    if (flags.dualInconsistent) {
      tags.push('票据异常')
      detailNote += `双轨比对入账凭证率仅 ${formatPercent(row.voucherRate)}，存在借贷试算不平迹象。`
    }
    if (!tags.length) tags.push('建设进度滞后')

    const isHigh = flags.dualInconsistent || tags.length >= 3 || tags.includes('超期挂账')
    result.push({
      ...baseFields(row),
      level: isHigh ? '高' : '中',
      tags,
      primaryIssue: tags[0] || '合规审查',
      detailNote,
    })
  }
  return result
}
