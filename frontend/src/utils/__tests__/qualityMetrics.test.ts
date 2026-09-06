import { describe, it, expect } from 'vitest'
import {
  calcComplianceRate,
  calcDualRunConsistency,
  buildQualityAuditList,
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
      expect(list[0].status).toBe('unknown')
    })
  })
})
