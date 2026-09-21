import { describe, expect, it } from 'vitest'
import {
  cleanProvinceName,
  createChinaMapLegendStops,
  createChinaMapOption,
  createChinaMapScale,
  createChinaMapScatterData,
  type ChinaMapDatum,
} from '../chinaMapOptions.ts'
import { chartPalette, mapRamp } from '../theme.ts'

const data: ChinaMapDatum[] = [
  { name: '广东', value: 40, total: 10, launched: 6, dual: 2 },
  { name: '江苏', value: 60, total: 8, launched: 5, dual: 1 },
]

describe('china map options', () => {
  it('normalizes province names and derives the padded legend scale', () => {
    expect(cleanProvinceName('新疆维吾尔自治区')).toBe('新疆')
    const scale = createChinaMapScale(data)
    expect(scale).toEqual({ min: 37, max: 63 })
    expect(createChinaMapLegendStops(scale)).toHaveLength(mapRamp.steps.length)
  })

  it('builds a live geo point only for known provinces', () => {
    const points = createChinaMapScatterData({
      province: '广东省',
      unitName: '广东单位',
      storyTitle: '凭证入账',
    })

    expect(points[0]).toMatchObject({
      name: '广东单位 · 凭证入账',
      province: '广东',
      actionText: '凭证入账',
    })
    expect(createChinaMapScatterData({ province: '未知地区' })).toEqual([])
  })

  it('keeps selection styling, live points, and tooltip facts in the option factory', () => {
    const scale = createChinaMapScale(data)
    const points = createChinaMapScatterData({ province: '广东', unitName: '广东单位' })
    const option = createChinaMapOption(data, ['广东', '江苏'], points, scale)

    expect(option.geo.regions[0].itemStyle.areaColor).toBe(chartPalette.accentDim)
    expect(option.geo.regions[1].itemStyle.areaColor).toBe(chartPalette.accentDim)
    expect(option.geo.selectedMode).toBe(false)
    expect(option.series[0].data).toEqual(points)

    const resetOption = createChinaMapOption(data, [], points, scale)
    expect(resetOption.geo.regions.every(region => region.itemStyle.areaColor !== chartPalette.accentDim)).toBe(true)

    const formatter = option.tooltip.formatter as (params: Record<string, unknown>) => string
    expect(formatter({ name: '江苏' })).toContain('纳管 8 家 · 上线 5 家 · 双轨 1 家')
    expect(formatter({ name: '西藏' })).toContain('暂无纳管单位')
  })
})
