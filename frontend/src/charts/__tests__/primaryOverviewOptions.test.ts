import { describe, expect, it } from 'vitest'
import {
  createDualRunOutcomeOption,
  createIntegrationOutcomeOption,
} from '../operationsOptions.ts'
import { createProvinceProfileOption } from '../panelOptions.ts'
import { createRolloutCommandOption } from '../rolloutOptions.ts'

describe('primary overview charts', () => {
  it('derives rollout backlog from the supplied totals', () => {
    const option = createRolloutCommandOption({ total: 200, launched: 80, dual: 30 })

    expect(option.series[0].data[0].value).toBe(40)
    expect(option.series[1].data.map((item) => item.value)).toEqual([90, 30, 80])
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

})
