import { calmAnimation, chartInk, chartPalette, chartTooltip } from './theme'
import { CHART_FONT } from './tokens'

export interface RiskOverviewItem {
  name: string
  value: number
  color: string
}

export function createRiskOverviewOption(items: RiskOverviewItem[]) {
  const max = Math.max(1, ...items.map((item) => item.value))
  return {
    ...calmAnimation,
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...chartTooltip },
    grid: { left: '16%', right: '14%', top: 7, bottom: 7 },
    xAxis: { type: 'value', max, show: false },
    yAxis: {
      type: 'category', data: items.map((item) => item.name),
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: chartInk.textMuted, fontSize: CHART_FONT.axis },
    },
    series: [{
      type: 'bar', barWidth: 11, showBackground: true,
      backgroundStyle: { color: chartInk.borderSoft, borderRadius: 3 },
      data: items.map((item) => ({ value: item.value, itemStyle: { color: item.color, borderRadius: 3 } })),
      label: {
        show: true, position: 'right', color: chartInk.textPrimary,
        fontFamily: 'monospace', fontSize: CHART_FONT.axis, formatter: '{c} 家',
      },
    }],
  }
}
