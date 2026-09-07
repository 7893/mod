import { calmAnimation, chartInk, chartPalette, chartTooltip } from './theme'

export interface ComplianceOverviewData {
  rate: number | null
  supervised: number
  high: number
  medium: number
}

export function createComplianceOverviewOption(data: ComplianceOverviewData) {
  const rate = data.rate ?? 0
  const levels = [
    { name: '重点监督', value: data.supervised, color: chartPalette.accent },
    { name: '中度瑕疵', value: data.medium, color: chartPalette.warning },
    { name: '高风险', value: data.high, color: chartPalette.danger },
  ]
  return {
    ...calmAnimation,
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...chartTooltip },
    grid: { left: '31%', right: 62, top: 7, bottom: 7 },
    xAxis: { type: 'value', max: Math.max(1, data.supervised), show: false },
    yAxis: {
      type: 'category', data: levels.map((item) => item.name),
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: chartInk.textMuted, fontSize: 9 },
    },
    series: [
      {
        type: 'gauge', startAngle: 210, endAngle: -30,
        center: ['14%', '54%'], radius: '82%', silent: true,
        pointer: { show: false },
        progress: { show: data.rate != null, roundCap: true, width: 9, itemStyle: { color: chartPalette.success } },
        axisLine: { lineStyle: { width: 9, color: [[1, chartInk.borderSoft]] } },
        axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false },
        title: { show: true, offsetCenter: [0, '42%'], color: chartInk.textMuted, fontSize: 9 },
        detail: {
          offsetCenter: [0, '-6%'], color: chartInk.textPrimary,
          fontFamily: 'monospace', fontSize: 17,
          formatter: data.rate == null ? '—' : '{value}%',
        },
        data: [{ value: rate, name: '全网合规率' }],
      },
      {
        type: 'bar', barWidth: 11, showBackground: true,
        backgroundStyle: { color: chartInk.borderSoft, borderRadius: 3 },
        data: levels.map((item) => ({ value: item.value, itemStyle: { color: item.color, borderRadius: 3 } })),
        label: {
          show: true, position: 'right', color: chartInk.textPrimary,
          fontFamily: 'monospace', fontSize: 9, formatter: '{c} 家',
        },
      },
    ],
  }
}
