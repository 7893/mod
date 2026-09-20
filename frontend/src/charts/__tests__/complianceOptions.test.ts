import { describe, expect, it } from 'vitest'
import { chartSeriesColors } from '../theme.ts'
import { CHART_FONT } from '../tokens.ts'
import { createComplianceTagOption } from '../complianceOptions.ts'

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
})
