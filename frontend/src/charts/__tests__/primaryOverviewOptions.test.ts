import { describe, expect, it } from 'vitest'
import { createComplianceOverviewOption } from '../complianceOptions.ts'
import { createRiskOverviewOption } from '../insightsOptions.ts'
import {
  createDualRunOutcomeOption,
  createIntegrationOutcomeOption,
  createOperationsFlowOption,
  createOperationsOverviewOption,
} from '../operationsOptions.ts'
import { createProvinceProfileOption } from '../panelOptions.ts'
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

  it('adds dual-run volume without duplicating labels outside the chart', () => {
    const option = createOperationsFlowOption({
      businessDocument: 400,
      accountingVoucher: 300,
      integrationResult: 200,
      dualRunResult: 100,
    })

    expect(option.yAxis.data).toEqual(['双轨核对', '接口集成', '会计凭证', '业务单据'])
    expect(option.series[0].data.map((item) => item.value)).toEqual([100, 200, 300, 400])
  })

  it('keeps integration and dual-run outcomes in compact two-row charts', () => {
    const integration = createIntegrationOutcomeOption(950, 50)
    const dualRun = createDualRunOutcomeOption(980, 20)

    expect(integration.series[0].data.map((item) => item.value)).toEqual([50, 950])
    expect(dualRun.series[0].data.map((item) => item.value)).toEqual([20, 980])
  })

  it('renders the A2 progress ring without placing text inside the small gauge', () => {
    const option = createProvinceProfileOption(64.2)
    const gauge = option.series[0]

    expect(gauge.data[0]).toEqual({ value: 64.2, name: '建设完成率' })
    expect(gauge.title.show).toBe(false)
    expect(gauge.detail.show).toBe(false)
  })

  it('shows an honest empty compliance gauge when the rate is absent', () => {
    const option = createComplianceOverviewOption({ rate: null, supervised: 10, high: 2, medium: 8 })
    const gauge = option.series[0]

    expect(gauge.progress?.show).toBe(false)
    expect(gauge.detail?.formatter).toBe('—')
    expect(option.series[1].data.map((item) => item.value)).toEqual([10, 8, 2])
  })

  it('uses the supplied risk inputs in the comparison bars without an overlapping center label', () => {
    const items = [
      { name: '甲', value: 3, color: '#111111' },
      { name: '乙', value: 5, color: '#222222' },
      { name: '丙', value: 2, color: '#333333' },
    ]
    const option = createRiskOverviewOption(items)

    expect(option.series[0].data.map((item) => item.value)).toEqual([3, 5, 2])
    expect('title' in option).toBe(false)
  })
})
