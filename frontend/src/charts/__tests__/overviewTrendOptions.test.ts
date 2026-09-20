import { describe, expect, it } from 'vitest'
import {
  createOverviewTrendOption,
  selectOverviewTrendWindow,
  type OverviewTrendPoint,
} from '../overviewTrendOptions'
import { CHART_FONT } from '../tokens'

const points: OverviewTrendPoint[] = Array.from({ length: 10 }, (_, index) => ({
  date: `09-${String(index + 1).padStart(2, '0')}`,
  fullDate: `2026-09-${String(index + 1).padStart(2, '0')}`,
  launched: 100 + index,
  dual: 20 + index,
}))

describe('overview trend options', () => {
  it('selects a seven-point window centered on the supplied date', () => {
    const selected = selectOverviewTrendWindow(points, new Date('2026-09-06T00:00:00Z'))

    expect(selected).toHaveLength(7)
    expect(selected[3]?.fullDate).toBe('2026-09-06')
  })

  it('uses shared chart typography and confined tooltip defaults', () => {
    const option = createOverviewTrendOption(points.slice(0, 7))

    expect(option.tooltip.confine).toBe(true)
    expect(option.xAxis.axisLabel.fontSize).toBe(CHART_FONT.axis)
    expect(option.yAxis.axisLabel.fontSize).toBe(CHART_FONT.axis)
  })
})
