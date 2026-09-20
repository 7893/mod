import { describe, expect, it } from 'vitest'
import {
  createOperationsVolumeOption,
  createProgressRingsOption,
  createRiskClosureOption,
} from '../cockpitTopBarOptions'
import { chartPalette, chartTooltip } from '../theme'
import { CHART_FONT } from '../tokens'

describe('cockpit top bar options', () => {
  it('maps construction and rollout percentages into complementary rings', () => {
    const option = createProgressRingsOption({ constructionProgress: 72.5, rolloutRate: 64 })

    expect(option.series[0].data.map((item) => item.value)).toEqual([72.5, 27.5])
    expect(option.series[1].data.map((item) => item.value)).toEqual([64, 36])
    expect(option.tooltip.confine).toBe(chartTooltip.confine)
  })

  it('keeps the compact operations order, palette and shared typography', () => {
    const option = createOperationsVolumeOption({ documents: 1200, vouchers: 800, integrations: 60 })

    expect(option.yAxis.data).toEqual(['接口集成', '会计凭证', '业务单据'])
    expect(option.series[0].data.map((item) => item.value)).toEqual([60, 800, 1200])
    expect(option.series[0].data.map((item) => item.itemStyle.color)).toEqual([
      chartPalette.warning,
      chartPalette.success,
      chartPalette.accent,
    ])
    expect(option.yAxis.axisLabel.fontSize).toBe(CHART_FONT.micro)
    expect(option.series[0].label.fontSize).toBe(CHART_FONT.micro)
    expect(option.series[0].label.formatter({ value: 1200 })).toBe('1,200')
  })

  it('maps resolved and unresolved counts without inventing fallback data', () => {
    const option = createRiskClosureOption({ resolved: 0, unresolved: 9 })

    expect(option.series[0].data.map((item) => item.value)).toEqual([0, 9])
    expect(option.series[0].data.map((item) => item.itemStyle.color)).toEqual([
      chartPalette.success,
      chartPalette.danger,
    ])
  })
})
