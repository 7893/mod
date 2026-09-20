import { describe, expect, it } from 'vitest'
import { chartPalette, chartSeriesColors } from '../theme.ts'
import { CHART_FONT } from '../tokens.ts'
import { createComplianceRiskOption, createComplianceTagOption } from '../complianceOptions.ts'

describe('compliance chart options', () => {
  it('keeps compliance tag order, values, and semantic colors together', () => {
    const option = createComplianceTagOption([
      { label: '超期挂账', count: 4 },
      { label: '超预算迹象', count: 3 },
      { label: '票据异常', count: 2 },
      { label: '准备期卡顿', count: 1 },
    ])

    expect(option.xAxis.data).toEqual(['超期挂账', '超预算迹象', '票据异常', '准备期卡顿'])
    expect(option.xAxis.axisLabel.fontSize).toBe(CHART_FONT.axis)
    expect(option.series[0].data).toEqual([
      { value: 4, itemStyle: { color: chartSeriesColors[3] } },
      { value: 3, itemStyle: { color: chartSeriesColors[4] } },
      { value: 2, itemStyle: { color: chartSeriesColors[2] } },
      { value: 1, itemStyle: { color: chartSeriesColors[1] } },
    ])
    expect(option.tooltip.confine).toBe(true)
  })

  it('formats risk composition labels from supplied counts', () => {
    const option = createComplianceRiskOption({ compliant: 1000, medium: 12, high: 3 })

    expect(option.series[0].data).toEqual([
      { value: 1000, name: '合规达标 (1,000)', itemStyle: { color: chartPalette.success } },
      { value: 12, name: '中度瑕疵 (12)', itemStyle: { color: chartPalette.warning } },
      { value: 3, name: '高风险隐患 (3)', itemStyle: { color: chartPalette.danger } },
    ])
    expect(option.tooltip.confine).toBe(true)
  })
})
