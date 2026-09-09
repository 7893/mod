import { formatCount } from '../formatters/metrics'
import { calmAnimation, chartInk, chartPalette, chartTooltip } from './theme'

export interface RolloutCommandSummary {
  total: number
  launched: number
  dual: number
}

export interface RolloutTrendPoint {
  date: string
  batchId: number
  name: string
  total: number
  launchedPct: number
  dualPct: number
}

export function createRolloutTrendMatrixOption(points: RolloutTrendPoint[]) {
  const dates = [...new Set(points.map((point) => point.date))]
  const batches = [...new Map(
    points.map((point) => [point.batchId, { id: point.batchId, name: point.name }]),
  ).values()].sort((a, b) => a.id - b.id)
  const matrix = points.map((point) => ({
    value: [dates.indexOf(point.date), batches.findIndex((batch) => batch.id === point.batchId), point.launchedPct],
    point,
  }))

  return {
    ...calmAnimation,
    tooltip: {
      trigger: 'item',
      ...chartTooltip,
      formatter: (params: any) => {
        const point = params.data?.point as RolloutTrendPoint | undefined
        return point
          ? `${point.date} · ${point.name}<br/>上线率 <b>${point.launchedPct}%</b><br/>双轨率 <b>${point.dualPct}%</b> · ${formatCount(point.total)} 家`
          : ''
      },
    },
    visualMap: {
      show: false, min: 0, max: 100, dimension: 2,
      inRange: { color: [chartInk.borderSoft, chartPalette.accent, chartPalette.success] },
    },
    grid: { left: 52, right: 10, top: 8, bottom: 28 },
    xAxis: {
      type: 'category', data: dates,
      axisLine: { lineStyle: { color: chartInk.border } }, axisTick: { show: false },
      axisLabel: { color: chartInk.textMuted, fontSize: 10 },
    },
    yAxis: {
      type: 'category', data: batches.map((batch) => batch.name),
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: chartInk.textMuted, fontSize: 10 },
    },
    series: [{
      type: 'heatmap', data: matrix,
      label: {
        show: true, color: chartInk.textPrimary, fontFamily: 'monospace', fontSize: 9,
        formatter: (params: any) => `${params.value?.[2] ?? 0}%`,
      },
      itemStyle: { borderColor: chartInk.bgTooltip, borderWidth: 2, borderRadius: 3 },
    }],
  }
}

export function createRolloutCommandOption(summary: RolloutCommandSummary) {
  const pending = Math.max(0, summary.total - summary.launched - summary.dual)
  const rate = summary.total > 0 ? Math.round((summary.launched * 1000) / summary.total) / 10 : 0
  const states = [
    { name: '待推进', value: pending, color: chartPalette.neutral },
    { name: '双轨运行', value: summary.dual, color: chartPalette.warning },
    { name: '已上线', value: summary.launched, color: chartPalette.success },
  ]

  return {
    ...calmAnimation,
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...chartTooltip },
    grid: { left: '31%', right: 72, top: 7, bottom: 7 },
    xAxis: { type: 'value', max: summary.total || 1, show: false },
    yAxis: {
      type: 'category', data: states.map((item) => item.name),
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: chartInk.textMuted, fontSize: 9 },
    },
    series: [
      {
        type: 'gauge', startAngle: 210, endAngle: -30,
        center: ['14%', '54%'], radius: '82%', silent: true,
        pointer: { show: false },
        progress: { show: true, roundCap: true, width: 9, itemStyle: { color: chartPalette.success } },
        axisLine: { lineStyle: { width: 9, color: [[1, chartInk.borderSoft]] } },
        axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false },
        title: { show: true, offsetCenter: [0, '42%'], color: chartInk.textMuted, fontSize: 9 },
        detail: {
          offsetCenter: [0, '-6%'], color: chartInk.textPrimary,
          fontFamily: 'monospace', fontSize: 17, formatter: '{value}%',
        },
        data: [{ value: rate, name: '总体上线率' }],
      },
      {
        type: 'bar', barWidth: 11, showBackground: true,
        backgroundStyle: { color: chartInk.borderSoft, borderRadius: 3 },
        data: states.map((item) => ({ value: item.value, itemStyle: { color: item.color, borderRadius: 3 } })),
        label: {
          show: true, position: 'right', color: chartInk.textPrimary,
          fontFamily: 'monospace', fontSize: 9,
          formatter: (params: any) => formatCount(params.value),
        },
      },
    ],
  }
}
