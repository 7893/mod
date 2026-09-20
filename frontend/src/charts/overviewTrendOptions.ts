import type { EChartsOption } from 'echarts'
import {
  calmAnimation,
  categoryAxis,
  chartInk,
  chartPalette,
  chartTooltip,
  valueAxis,
} from './theme'
import { CHART_FONT } from './tokens'

export interface OverviewTrendPoint {
  date: string
  fullDate?: string
  launched: number
  dual?: number
}

export function selectOverviewTrendWindow(
  data: OverviewTrendPoint[],
  now = new Date(),
): OverviewTrendPoint[] {
  if (data.length <= 7) return data

  const mm = String(now.getMonth() + 1).padStart(2, '0')
  const dd = String(now.getDate()).padStart(2, '0')
  const todayDate = `${mm}-${dd}`
  const todayFullDate = `${now.getFullYear()}-${todayDate}`
  const match = data.findIndex(
    (item) => item.fullDate === todayFullDate || item.date === todayDate,
  )
  const center = match === -1 ? Math.floor(data.length / 2) : match
  const start = Math.max(0, Math.min(center - 3, data.length - 7))
  return data.slice(start, start + 7)
}

export function createOverviewTrendOption(data: OverviewTrendPoint[], now = new Date()) {
  const list = selectOverviewTrendWindow(data, now)
  return {
    ...calmAnimation,
    tooltip: { trigger: 'axis', ...chartTooltip },
    grid: { top: 6, bottom: 22, left: 38, right: 12 },
    xAxis: {
      ...categoryAxis,
      data: list.map((item) => item.date),
      boundaryGap: false,
      axisLabel: {
        color: chartInk.textDim,
        fontSize: CHART_FONT.axis,
        fontFamily: 'monospace',
      },
    },
    yAxis: {
      ...valueAxis,
      min: 0,
      splitNumber: 3,
      axisLabel: {
        color: chartInk.textDim,
        fontSize: CHART_FONT.axis,
        fontFamily: 'monospace',
      },
      splitLine: { lineStyle: { color: chartInk.borderSoft, type: 'dashed' as const } },
    },
    series: [
      {
        name: '已上线',
        type: 'line',
        smooth: true,
        data: list.map((item) => item.launched),
        showSymbol: false,
        lineStyle: { color: chartPalette.accent, width: 2.2 },
      },
      {
        name: '双轨核对',
        type: 'bar',
        barMaxWidth: 18,
        data: list.map((item) => item.dual ?? 0),
        itemStyle: {
          color: chartPalette.warning,
          borderRadius: [3, 3, 0, 0],
          opacity: 0.82,
        },
      },
    ],
  } satisfies EChartsOption
}
