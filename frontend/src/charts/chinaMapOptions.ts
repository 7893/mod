import type { EChartsOption } from 'echarts'
import { chartInk, chartPalette, mapRamp } from './theme'
import { CHART_FONT } from './tokens'

export interface ChinaMapDatum {
  name: string
  value: number
  total: number
  launched: number
  dual: number
  constructionPct?: number
  todayAdded?: number
  docsTodayAdded?: number
  docsAddedAsOfDate?: string
  addedAsOfDate?: string
}

export interface ChinaMapLiveEvent {
  province?: string
  unitName?: string
  storyTitle?: string
}

export interface ChinaMapScale {
  min: number
  max: number
}

export interface ChinaMapScatterPoint {
  name: string
  value: [number, number, number]
  unitName: string
  province: string
  actionText: string
}

const PROVINCE_CENTERS: Record<string, [number, number]> = {
  '北京': [116.405, 39.905],
  '天津': [117.190, 39.126],
  '河北': [114.502, 38.045],
  '山西': [112.549, 37.857],
  '内蒙古': [111.671, 40.818],
  '辽宁': [123.429, 41.797],
  '吉林': [125.325, 43.887],
  '黑龙江': [126.642, 45.757],
  '上海': [121.473, 31.232],
  '江苏': [118.767, 32.042],
  '浙江': [120.154, 30.287],
  '安徽': [117.283, 31.861],
  '福建': [119.306, 26.075],
  '江西': [115.892, 28.676],
  '山东': [117.001, 36.676],
  '河南': [113.665, 34.758],
  '湖北': [114.299, 30.584],
  '湖南': [112.982, 28.194],
  '广东': [113.281, 23.125],
  '广西': [108.320, 22.824],
  '海南': [110.331, 20.032],
  '重庆': [106.505, 29.533],
  '四川': [104.066, 30.659],
  '贵州': [106.713, 26.578],
  '云南': [102.712, 25.041],
  '西藏': [91.132, 29.660],
  '陕西': [108.948, 34.263],
  '甘肃': [103.824, 36.058],
  '青海': [101.779, 36.623],
  '宁夏': [106.278, 38.466],
  '新疆': [87.618, 43.793],
  '香港': [114.173, 22.320],
  '澳门': [113.549, 22.199],
  '台湾': [121.509, 25.044],
}

export function cleanProvinceName(raw?: string): string {
  if (!raw) return ''
  return raw.replace(/(省|市|自治区|壮族|回族|维吾尔|特别行政区)/g, '').trim()
}

export function createChinaMapScale(data: ChinaMapDatum[]): ChinaMapScale {
  const values = data.map((item) => Number(item.value)).filter(Number.isFinite)
  const dataMin = values.length ? Math.min(...values) : 0
  const dataMax = values.length ? Math.max(...values) : 100
  const padding = Math.max(2, (dataMax - dataMin) * 0.12)
  return {
    min: Math.max(0, Math.floor(dataMin - padding)),
    max: Math.min(100, Math.ceil(dataMax + padding)),
  }
}

export function createChinaMapLegendStops(scale: ChinaMapScale) {
  const step = (scale.max - scale.min) / mapRamp.steps.length
  return mapRamp.steps.map((color, index) => ({
    color,
    from: Math.round(scale.min + step * index),
    to: Math.round(scale.min + step * (index + 1)),
  }))
}

export function createChinaMapScatterData(event?: ChinaMapLiveEvent | null): ChinaMapScatterPoint[] {
  if (!event?.province) return []
  const province = cleanProvinceName(event.province)
  const coordinates = PROVINCE_CENTERS[province]
  if (!coordinates) return []
  const actionText = event.storyTitle || '实时动态'
  return [{
    name: `${event.unitName || province} · ${actionText}`,
    value: [coordinates[0], coordinates[1], 100],
    unitName: event.unitName || province,
    province,
    actionText,
  }]
}

function colorFor(value: number, scale: ChinaMapScale) {
  if (!Number.isFinite(value)) return mapRamp.noData
  const ratio = scale.max === scale.min ? 0 : (value - scale.min) / (scale.max - scale.min)
  const index = Math.min(
    mapRamp.steps.length - 1,
    Math.max(0, Math.round(ratio * (mapRamp.steps.length - 1))),
  )
  return mapRamp.steps[index]
}

export function createChinaMapOption(
  data: ChinaMapDatum[],
  selected: readonly string[] | undefined,
  scatterData: ChinaMapScatterPoint[],
  scale: ChinaMapScale,
) {
  return {
    backgroundColor: 'transparent',
    tooltip: {
      confine: true,
      trigger: 'item',
      padding: 0,
      borderWidth: 0,
      backgroundColor: 'transparent',
      formatter: (params: any) => {
        if (params.componentType === 'series' && params.seriesType === 'effectScatter') {
          const point = params.data as ChinaMapScatterPoint
          return `<div class="map-tip">
            <b>${point.unitName}</b>
            <span style="color:${chartPalette.accent}">${point.actionText}</span>
            <i>所属省份：${point.province}</i>
          </div>`
        }
        const item = data.find((value) => value.name === params.name)
        if (!item) return `<div class="map-tip"><b>${params.name}</b><span>暂无纳管单位</span></div>`
        return `<div class="map-tip">
          <b>${params.name}</b>
          <span>建设完成度 ${item.value || item.constructionPct || 0}%</span>
          <i>纳管 ${item.total} 家 · 上线 ${item.launched} 家 · 双轨 ${item.dual} 家</i>
        </div>`
      },
    },
    geo: {
      map: 'MOD_CHINA',
      roam: false,
      zoom: 1.2,
      top: 8,
      bottom: 34,
      left: 8,
      right: 8,
      regions: data.map((item) => {
        const isSelected = selected?.includes(item.name) ?? false
        return {
          name: item.name,
          itemStyle: {
            areaColor: isSelected ? chartPalette.accentDim : colorFor(Number(item.value), scale),
            borderColor: isSelected ? chartPalette.accent : chartInk.border,
            borderWidth: isSelected ? 2 : 0.8,
          },
        }
      }),
      itemStyle: { areaColor: mapRamp.noData, borderColor: chartInk.border, borderWidth: 0.8 },
      emphasis: {
        itemStyle: { areaColor: chartPalette.accent },
        label: { show: true, color: chartInk.onAccent, fontWeight: 600 },
      },
      selectedMode: false,
      label: { show: false },
    },
    series: [{
      type: 'effectScatter',
      coordinateSystem: 'geo',
      data: scatterData,
      symbolSize: 14,
      rippleEffect: { scale: 6, period: 2.2, brushType: 'stroke', color: chartPalette.accent },
      itemStyle: { color: chartPalette.accent },
      label: {
        show: true,
        position: 'top',
        distance: 10,
        formatter: '{b}',
        color: chartInk.textPrimary,
        backgroundColor: chartInk.bgTooltip,
        borderColor: chartPalette.accent,
        borderWidth: 1,
        borderRadius: 4,
        padding: [4, 8],
        fontSize: CHART_FONT.caption,
        fontWeight: 'bold',
      },
      zlevel: 10,
    }],
  } satisfies EChartsOption
}
