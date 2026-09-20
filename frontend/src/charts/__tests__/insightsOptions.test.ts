import { describe, expect, it } from 'vitest'
import { createModelQualityOption, createRiskDimensionOption } from '../insightsOptions.ts'
import { chartPalette } from '../theme.ts'

describe('insights chart options', () => {
  it('keeps risk dimensions, tones, and tooltip facts aligned after display reversal', () => {
    const option = createRiskDimensionOption([
      {
        id: 'warning', type: '准备卡顿', count: 2, highCount: 1,
        batchDistribution: { '第一批': 2 }, gate: '第 4 批及以前', tone: 'warning',
      },
      {
        id: 'danger', type: '双轨核对差异', count: 3, highCount: 2,
        batchDistribution: {}, gate: '凭证率 < 95%', tone: 'danger',
      },
    ], 10)

    expect(option.yAxis.data).toEqual(['双轨核对差异', '准备卡顿'])
    expect(option.series[0].data).toEqual([
      { value: 3, itemStyle: { borderRadius: [0, 4, 4, 0], color: chartPalette.danger } },
      { value: 2, itemStyle: { borderRadius: [0, 4, 4, 0], color: chartPalette.warning } },
    ])
    const formatter = option.tooltip.formatter as (params: { dataIndex: number }) => string
    expect(formatter({ dataIndex: 0 })).toContain('预警规模:')
    expect(formatter({ dataIndex: 0 })).toContain('(30.0%)')
    expect(formatter({ dataIndex: 0 })).toContain('暂无集中批次')
  })

  it('renders an honest empty model gauge and formats evaluated quality', () => {
    const empty = createModelQualityOption({ quality: null, target: 'daily_amount', ready: false })
    expect(empty.series[0].progress.show).toBe(false)
    expect(empty.series[0].detail.formatter).toBe('—')

    const evaluated = createModelQualityOption({ quality: 0.87654, target: 'daily_amount', ready: true })
    expect(evaluated.series[0].data[0].value).toBeCloseTo(87.654)
    expect(evaluated.series[0].detail.formatter).toBe('R² 0.8765')
    expect(evaluated.series[0].progress.itemStyle.color).toBe(chartPalette.success)
  })
})
