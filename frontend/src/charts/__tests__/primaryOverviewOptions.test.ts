import { describe, expect, it } from 'vitest'
import { createComplianceOverviewOption } from '../complianceOptions.ts'
import { createRiskOverviewOption } from '../insightsOptions.ts'
import { createOperationsOverviewOption } from '../operationsOptions.ts'
import { createRolloutCommandOption } from '../rolloutOptions.ts'

describe('primary overview charts', () => {
  it('derives rollout backlog from the supplied totals', () => {
    const option = createRolloutCommandOption({ total: 200, launched: 80, dual: 30 })

    expect(option.series[0].data[0].value).toBe(40)
    expect(option.series[1].data.map((item) => item.value)).toEqual([90, 30, 80])
  })

  it('keeps operation volumes in their named order', () => {
    const option = createOperationsOverviewOption({
      businessDocument: 300,
      accountingVoucher: 200,
      integrationResult: 100,
    })

    expect(option.yAxis.data).toEqual(['接口集成', '会计凭证', '业务单据'])
    expect(option.series[0].data.map((item) => item.value)).toEqual([100, 200, 300])
  })

  it('shows an honest empty compliance gauge when the rate is absent', () => {
    const option = createComplianceOverviewOption({ rate: null, supervised: 10, high: 2, medium: 8 })
    const gauge = option.series[0]

    expect(gauge.progress?.show).toBe(false)
    expect(gauge.detail?.formatter).toBe('—')
    expect(option.series[1].data.map((item) => item.value)).toEqual([10, 8, 2])
  })

  it('uses the same risk inputs for the ring and comparison bars', () => {
    const items = [
      { name: '甲', value: 3, color: '#111111' },
      { name: '乙', value: 5, color: '#222222' },
      { name: '丙', value: 2, color: '#333333' },
    ]
    const option = createRiskOverviewOption(items)

    expect(option.title.text).toBe('10')
    expect(option.series[0].data.map((item) => item.value)).toEqual([3, 5, 2])
    expect(option.series[1].data.map((item) => item.value)).toEqual([3, 5, 2])
  })
})
