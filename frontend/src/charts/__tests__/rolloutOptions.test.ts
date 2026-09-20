import { describe, expect, it } from 'vitest'
import { createProvinceRolloutOption } from '../rolloutOptions'
import { chartInk, chartPalette } from '../theme'
import { CHART_FONT } from '../tokens'

describe('rollout options', () => {
  it('keeps province rollout volumes aligned by status and province', () => {
    const option = createProvinceRolloutOption([
      { name: '甲省', launched: 80, dual: 15, unlaunched: 5 },
      { name: '乙省', launched: 60, dual: 20, unlaunched: 20 },
    ])

    expect(option.xAxis.data).toEqual(['甲省', '乙省'])
    expect(option.series.map((series) => series.name)).toEqual(['已上线', '双轨', '其他'])
    expect(option.series.map((series) => series.data)).toEqual([
      [80, 60],
      [15, 20],
      [5, 20],
    ])
    expect(option.series.map((series) => series.itemStyle.color)).toEqual([
      chartPalette.accent,
      chartPalette.warning,
      chartInk.border,
    ])
    expect(option.xAxis.axisLabel.fontSize).toBe(CHART_FONT.axis)
    expect(option.tooltip.confine).toBe(true)
  })
})
