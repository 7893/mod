import { describe, it, expect } from 'vitest'
import {
  calcComplianceRate,
  calcDualRunConsistency,
  buildQualityAuditList,
  buildRiskDimensionBreakdown,
} from '../qualityMetrics'

describe('utils/qualityMetrics', () => {
  describe('calcComplianceRate', () => {
    it('returns 100% when errors count is 0', () => {
      expect(calcComplianceRate(1000, 0)).toBe(100)
      expect(calcComplianceRate(2318199, 0)).toBe(100)
    })

    it('returns correct rounded percentage when errors exist', () => {
      expect(calcComplianceRate(1000, 10)).toBe(99)
      expect(calcComplianceRate(200, 1)).toBe(99.5)
    })

    it('handles boundary cases honestly', () => {
      expect(calcComplianceRate(100, 150)).toBe(0)
      expect(calcComplianceRate(0, 0)).toBeNull()
      expect(calcComplianceRate(-5, 0)).toBeNull()
      expect(calcComplianceRate(100, -1)).toBeNull()
      expect(calcComplianceRate(null, 0)).toBeNull()
      expect(calcComplianceRate(100, null)).toBeNull()
    })
  })

  describe('calcDualRunConsistency', () => {
    it('calculates consistent and inconsistent counts and consistency percentage', () => {
      const res = calcDualRunConsistency(29058, 28277, 2310)
      expect(res).toEqual({
        consistent: 28277,
        inconsistent: 2310,
        consistencyPct: 97.31,
      })
    })

    it('infers inconsistent count if omitted', () => {
      const res = calcDualRunConsistency(1000, 950, null)
      expect(res).toEqual({
        consistent: 950,
        inconsistent: 50,
        consistencyPct: 95,
      })
    })

    it('returns null on invalid or missing inputs', () => {
      expect(calcDualRunConsistency(0, 0, 0)).toBeNull()
      expect(calcDualRunConsistency(null, 10, 0)).toBeNull()
      expect(calcDualRunConsistency(100, null, 0)).toBeNull()
    })

    it('prevents consistency percentage exceeding 100% when total lags behind consistent (KI-069)', () => {
      // 滞后快照场景：total (29056) 小于实时一致数 (29827)
      const res = calcDualRunConsistency(29056, 29827, 2310)
      expect(res).not.toBeNull()
      expect(res!.consistent).toBe(29827)
      expect(res!.inconsistent).toBe(2310)
      expect(res!.consistencyPct).toBeLessThanOrEqual(100)
      expect(res!.consistencyPct).toBe(100)
    })
  })

  describe('buildQualityAuditList', () => {
    it('builds 4 gold standard items from snapshot and ops data', () => {
      const list = buildQualityAuditList(
        {
          voucherBalanceErrors: 0,
          timeOrderErrors: 0,
          orphanLinkErrors: 0,
          organizationsWithStatusProgression: 2000,
        },
        {
          accountingVoucher: 1471150,
          businessDocument: 2318199,
          documentVoucherLink: 1471150,
        },
        2000,
      )

      expect(list).toHaveLength(4)
      expect(list.map((i) => i.rule)).toEqual([
        '借贷平衡核验',
        '时序逻辑核验',
        '孤儿链路核验',
        '状态演进追踪',
      ])
      expect(list.every((i) => i.errors === 0)).toBe(true)
      expect(list.every((i) => i.rate === 100)).toBe(true)
      expect(list.every((i) => i.status === 'pass')).toBe(true)
    })

    it('handles missing or partial quality gracefully without fabricating data', () => {
      const list = buildQualityAuditList(null, null, null)
      expect(list).toHaveLength(4)
      expect(list[0].errors).toBeNull()
      expect(list[0].total).toBeNull()
      expect(list[0].rate).toBeNull()
      expect(list[0].status).toBe('unknown')
      expect(list[3]).toMatchObject({ errors: null, total: null, rate: null, status: 'unknown' })
    })
  })

  const RULES = {
    lifecycle: { dualRunConsistencyRateMin: 98 },
    risk: { constructionLagRate: 88, constructionCriticalRate: 80, lastActiveBatchId: 7 },
  }

  describe('buildRiskDimensionBreakdown', () => {
    it('aggregates counts and batch distributions accurately', () => {
      const mockUnits = [
        { riskType: '准备期卡顿', riskLevel: '重点关注', batch: '第六批' },
        { riskType: '准备期卡顿', riskLevel: '重点关注', batch: '第六批' },
        { riskType: '双轨核对差异', riskLevel: '高危', batch: '第六批' },
        { riskType: '建设严重滞后', riskLevel: '高危', batch: '第五批' },
      ]

      const res = buildRiskDimensionBreakdown(mockUnits, RULES)
      expect(res).toHaveLength(3)

      const prep = res.find((r) => r.type === '准备期卡顿')
      expect(prep?.count).toBe(2)
      expect(prep?.batchDistribution).toEqual({ 第六批: 2 })

      const dual = res.find((r) => r.type === '双轨核对差异')
      expect(dual?.count).toBe(1)
      expect(dual?.batchDistribution).toEqual({ 第六批: 1 })

      const lag = res.find((r) => r.type === '建设严重滞后')
      expect(lag?.count).toBe(1)
      expect(lag?.batchDistribution).toEqual({ 第五批: 1 })
      expect(lag?.gate).toBe('建设度 < 88%（< 80% 为高危）')
      expect(dual?.gate).toBe('双轨凭证率 < 98%')
    })

    it('counts high-risk units per dimension from unit-level levels', () => {
      const res = buildRiskDimensionBreakdown([
        { riskType: '建设严重滞后', riskLevel: '高危', batch: '第六批' },
        { riskType: '建设严重滞后', riskLevel: '重点关注', batch: '第六批' },
      ], RULES)
      const lag = res.find((r) => r.type === '建设严重滞后')
      expect(lag?.count).toBe(2)
      expect(lag?.highCount).toBe(1)
    })

    it('returns zero counts safely on empty or null inputs', () => {
      const res = buildRiskDimensionBreakdown(null, RULES)
      expect(res).toHaveLength(3)
      expect(res.every((r) => r.count === 0)).toBe(true)
    })
  })
})
