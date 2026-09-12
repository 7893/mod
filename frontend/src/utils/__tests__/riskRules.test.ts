import { describe, it, expect } from 'vitest'
import type { EntityRow } from '../../stores/project'
import {
  deriveAtRiskUnits,
  deriveComplianceUnits,
  evaluateRiskFlags,
  indexPredictions,
  type BusinessRules,
} from '../riskRules'

const rules: BusinessRules = {
  lifecycle: {
    dualRunConsistencyRateMin: 98,
    orgStages: ['未启动', '准备中', '双轨运行', '已上线', '稳定运行'],
    launchedStatuses: ['已上线', '稳定运行'],
    displayStatuses: ['未启动', '准备中', '双轨运行', '已上线'],
  },
  risk: { constructionLagRate: 88, constructionCriticalRate: 80, openingDataLagRate: 88, lastActiveBatchId: 7 },
}

function row(partial: Partial<EntityRow>): EntityRow {
  return {
    id: 1,
    name: '单位',
    province: '北京',
    batch: '第一批',
    batchId: 1,
    owner: '张三',
    status: '已上线',
    construction: 100,
    openingData: 100,
    voucherRate: 100,
    ...partial,
  } as EntityRow
}

describe('evaluateRiskFlags', () => {
  it('flags dual-run inconsistency only for dual-run units below the gate', () => {
    expect(evaluateRiskFlags(row({ status: '双轨运行', voucherRate: 90 }), rules).dualInconsistent).toBe(true)
    expect(evaluateRiskFlags(row({ status: '双轨运行', voucherRate: null }), rules).dualInconsistent).toBe(false)
    expect(evaluateRiskFlags(row({ status: '已上线', voucherRate: 50 }), rules).dualInconsistent).toBe(false)
  })

  it('flags construction/opening-data lag only for dual-run units', () => {
    const lagging = evaluateRiskFlags(row({ status: '双轨运行', construction: 50, openingData: 50 }), rules)
    expect(lagging.constructionLag).toBe(true)
    expect(lagging.openingDataLag).toBe(true)
    const done = evaluateRiskFlags(row({ status: '已上线', construction: 50, openingData: 50 }), rules)
    expect(done.constructionLag).toBe(false)
    expect(done.openingDataLag).toBe(false)
    const preparing = evaluateRiskFlags(row({ status: '准备中', construction: 50, openingData: 50 }), rules)
    expect(preparing.constructionLag).toBe(false)
    expect(preparing.openingDataLag).toBe(false)
  })

  it('flags stuck preparation for batches at or before the last active one', () => {
    expect(evaluateRiskFlags(row({ status: '准备中', batchId: 7 }), rules).prepStuck).toBe(true)
    expect(evaluateRiskFlags(row({ status: '准备中', batchId: 8 }), rules).prepStuck).toBe(false)
    expect(evaluateRiskFlags(row({ status: '准备中', batchId: undefined }), rules).prepStuck).toBe(false)
  })
})

describe('deriveAtRiskUnits', () => {
  it('assigns each unit its single most severe risk type and merges predictions', () => {
    const rows = [
      row({ id: 1, status: '双轨运行', voucherRate: 90, construction: 50 }),
      row({ id: 2, status: '双轨运行', construction: 70 }),
      row({ id: 3, status: '双轨运行', construction: 85 }),
      row({ id: 4, status: '准备中', batchId: 3 }),
      row({ id: 5 }),
    ]
    const preds = indexPredictions([{ orgId: '2', stagnantDays: 12 }, null, { noId: true }])
    const units = deriveAtRiskUnits(rows, rules, preds)
    expect(units.map((u) => [u.id, u.riskType, u.riskLevel])).toEqual([
      [1, '双轨核对差异', '高危'],
      [2, '建设严重滞后', '高危'],
      [3, '建设严重滞后', '重点关注'],
      [4, '准备期卡顿', '重点关注'],
    ])
    expect(units[1].stagnantDays).toBe(12)
    expect(units[0].reason).toContain('98%')
    expect(units[1].reason).toContain('低于 88% 滞后门禁')
    expect(units[3].reason).toContain('第 7 批')
  })
})

describe('deriveComplianceUnits', () => {
  it('stacks tags, grades severity and skips compliant units', () => {
    const units = deriveComplianceUnits(
      [
        row({ id: 1, status: '双轨运行', voucherRate: 90, construction: 50, openingData: 50 }),
        row({ id: 2, status: '双轨运行', construction: 70 }),
        row({ id: 3, status: '准备中', batchId: 2 }),
        row({ id: 4 }),
      ],
      rules,
    )
    expect(units.map((u) => u.id)).toEqual([1, 2, 3])
    expect(units[0].tags).toEqual(['超期挂账', '超预算迹象', '票据异常'])
    expect(units[0].level).toBe('高')
    expect(units[1].tags).toEqual(['超预算迹象'])
    expect(units[1].level).toBe('中')
    expect(units[2].tags).toEqual(['准备期卡顿'])
    expect(units[2].primaryIssue).toBe('准备期卡顿')
  })
})

it('does not overwrite classifier features with regression results for the same unit', () => {
  const map = indexPredictions([
    { orgId: 8, model: 'MOD_RISK_CLASSIFIER', stagnantDays: 9 },
    { orgId: 8, model: 'MOD_REGRESSION_MODEL' },
  ])
  expect(map.get(8)?.stagnantDays).toBe(9)
})
