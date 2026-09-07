import { calmAnimation, chartInk, chartPalette, chartTooltip } from './theme'

export interface RolloutCommandSummary {
  total: number
  launched: number
  dual: number
}

export function createRolloutCommandOption(summary: RolloutCommandSummary) {
  const pending = Math.max(0, summary.total - summary.launched - summary.dual)
  const rate = summary.total > 0 ? Math.round((summary.launched * 1000) / summary.total) / 10 : 0
  const states = [
    { name: '待推进', value: pending, color: chartPalette.neutral },
    { name: '双轨运行', value: summary.dual, color: chartPalette.warning },
    { name: '正式上线', value: summary.launched, color: chartPalette.success },
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
          formatter: (params: any) => Number(params.value).toLocaleString(),
        },
      },
    ],
  }
}
