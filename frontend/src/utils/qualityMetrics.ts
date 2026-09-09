/**
 * 质量核验与双轨核对纯函数工具集
 * 严守诚实原则：缺失数据返回 null/—，0 值如实展示，绝不编造虚假数字
 */

export interface QualityAuditItem {
  id: string
  rule: string
  target: string
  errors: number | null
  total: number | null
  unit: string
  rate: number | null
  status: 'pass' | 'warning' | 'error' | 'unknown'
  hint: string
}

/**
 * 计算校验合规率（百分比）
 * @param total 校验总样本数
 * @param errors 检出异常数
 */
export function calcComplianceRate(total: number | null | undefined, errors: number | null | undefined): number | null {
  if (total === null || total === undefined || !Number.isFinite(total) || total <= 0) {
    return null
  }
  if (errors === null || errors === undefined || !Number.isFinite(errors) || errors < 0) {
    return null
  }
  const valid = Math.max(0, total - errors)
  const rate = (valid / total) * 100
  return Math.max(0, Math.min(100, Math.round(rate * 100) / 100))
}

/**
 * 校验双轨一致率
 * @param total 核对总笔数
 * @param consistent 一致笔数
 * @param inconsistent 不一致笔数
 */
export function calcDualRunConsistency(
  total: number | null | undefined,
  consistent: number | null | undefined,
  inconsistent: number | null | undefined,
): { consistent: number; inconsistent: number; consistencyPct: number } | null {
  if (total === null || total === undefined || !Number.isFinite(total) || total <= 0) {
    return null
  }
  if (consistent === null || consistent === undefined || !Number.isFinite(consistent)) {
    return null
  }
  const c = Math.max(0, consistent)
  // KI-069: 分子分母严格同源防护，若传入 total 小于 consistent 则自动归一，确保一致率 ∈ [0, 100]
  const safeTotal = Math.max(total, c)
  const inc = inconsistent !== null && inconsistent !== undefined && Number.isFinite(inconsistent)
    ? Math.max(0, inconsistent)
    : Math.max(0, safeTotal - c)
  const pct = Math.max(0, Math.min(100, Math.round((c / safeTotal) * 10000) / 100))
  return {
    consistent: c,
    inconsistent: inc,
    consistencyPct: pct,
  }
}

/**
 * 构建 D7 金标准核验项明细
 */
export function buildQualityAuditList(
  quality?: {
    voucherBalanceErrors?: number | null
    timeOrderErrors?: number | null
    orphanLinkErrors?: number | null
    organizationsWithStatusProgression?: number | null
  } | null,
  ops?: {
    accountingVoucher?: number | null
    businessDocument?: number | null
    documentVoucherLink?: number | null
  } | null,
  orgTotal?: number | null,
): QualityAuditItem[] {
  const vErrors = quality?.voucherBalanceErrors ?? null
  const tErrors = quality?.timeOrderErrors ?? null
  const oErrors = quality?.orphanLinkErrors ?? null
  const orgProg = quality?.organizationsWithStatusProgression ?? null

  const vTotal = ops?.accountingVoucher ?? null
  const dTotal = ops?.businessDocument ?? null
  const lTotal = ops?.documentVoucherLink ?? null
  const orgCount = orgTotal ?? null
  const progressionErrors = orgCount != null && orgProg != null
    ? Math.max(0, orgCount - orgProg)
    : null

  return [
    {
      id: 'voucher-balance',
      rule: '借贷平衡核验',
      target: '凭证借贷试算平衡',
      errors: vErrors,
      total: vTotal,
      unit: '张凭证',
      rate: vTotal != null && vErrors != null ? calcComplianceRate(vTotal, vErrors) : null,
      status: vErrors === 0 ? 'pass' : (vErrors != null && vErrors > 0 ? 'warning' : 'unknown'),
      hint: '严格校验凭证主表与分录借贷总额一致，杜绝单边账',
    },
    {
      id: 'time-order',
      rule: '时序逻辑核验',
      target: '提交→审批→制证递进',
      errors: tErrors,
      total: dTotal,
      unit: '笔单据',
      rate: dTotal != null && tErrors != null ? calcComplianceRate(dTotal, tErrors) : null,
      status: tErrors === 0 ? 'pass' : (tErrors != null && tErrors > 0 ? 'warning' : 'unknown'),
      hint: '核验业务单据全链路流转时间戳顺序，无时间倒流',
    },
    {
      id: 'orphan-link',
      rule: '孤儿链路核验',
      target: '单据凭证拓扑完整',
      errors: oErrors,
      total: lTotal,
      unit: '条关联',
      rate: lTotal != null && oErrors != null ? calcComplianceRate(lTotal, oErrors) : null,
      status: oErrors === 0 ? 'pass' : (oErrors != null && oErrors > 0 ? 'warning' : 'unknown'),
      hint: '核查业务拓扑映射，无孤儿断链或悬空记录',
    },
    {
      id: 'status-progression',
      rule: '状态演进追踪',
      target: '全周期状态快照跟踪',
      errors: progressionErrors,
      total: orgCount,
      unit: '家单位',
      rate: orgCount != null && orgCount > 0 && orgProg != null
        ? Math.max(0, Math.min(100, Math.round((orgProg / orgCount) * 100)))
        : null,
      status: progressionErrors === 0
        ? 'pass'
        : (progressionErrors != null && progressionErrors > 0 ? 'warning' : 'unknown'),
      hint: '历史快照跟踪生命周期演进，状态单向闭环达标',
    },
  ]
}

export interface RiskDimensionSummary {
  id: string
  type: string
  count: number
  level: '高危' | '重点关注'
  batchDistribution: Record<string, number>
  gate: string
  tone: 'danger' | 'warning' | 'accent'
}

/**
 * 汇总 F3 风险维度分布统计
 */
export function buildRiskDimensionBreakdown(
  units: Array<{
    riskType: string
    riskLevel?: string
    batch?: string
  }> | null | undefined,
): RiskDimensionSummary[] {
  const safeUnits = Array.isArray(units) ? units : []

  const counts: Record<string, number> = {
    准备期卡顿: 0,
    双轨核对差异: 0,
    建设严重滞后: 0,
  }
  const batches: Record<string, Record<string, number>> = {
    准备期卡顿: {},
    双轨核对差异: {},
    建设严重滞后: {},
  }

  safeUnits.forEach((u) => {
    if (u && u.riskType && counts[u.riskType] !== undefined) {
      counts[u.riskType] += 1
      const b = u.batch || '其他批次'
      batches[u.riskType][b] = (batches[u.riskType][b] || 0) + 1
    }
  })

  return [
    {
      id: 'prep-stuck',
      type: '准备期卡顿',
      count: counts['准备期卡顿'],
      level: '重点关注',
      batchDistribution: batches['准备期卡顿'],
      gate: '准备期停留超时，期初数据收集受阻',
      tone: 'warning',
    },
    {
      id: 'dual-diff',
      type: '双轨核对差异',
      count: counts['双轨核对差异'],
      level: '高危',
      batchDistribution: batches['双轨核对差异'],
      gate: '双轨凭证率 < 95%，借贷试算不平',
      tone: 'danger',
    },
    {
      id: 'const-lag',
      type: '建设严重滞后',
      count: counts['建设严重滞后'],
      level: '高危',
      batchDistribution: batches['建设严重滞后'],
      gate: '建设度 < 88%，落后批次推进均值',
      tone: 'accent',
    },
  ]
}
