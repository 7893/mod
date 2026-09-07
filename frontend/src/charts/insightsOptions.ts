import { calmAnimation, chartInk, chartPalette, chartTooltip } from './theme'

export interface RiskOverviewItem {
  name: string
  value: number
  color: string
}

export function createRiskOverviewOption(items: RiskOverviewItem[]) {
  const total = items.reduce((sum, item) => sum + item.value, 0)
  return {
    ...calmAnimation,
    tooltip: { trigger: 'item', ...chartTooltip },
    title: {
      text: total.toLocaleString(), subtext: '风险单位', left: '18%', top: '30%', textAlign: 'center',
      textStyle: { color: chartInk.textPrimary, fontFamily: 'monospace', fontSize: 17 },
      subtextStyle: { color: chartInk.textMuted, fontSize: 9 },
    },
    grid: { left: '42%', right: 58, top: 7, bottom: 7 },
    xAxis: { type: 'value', max: Math.max(1, total), show: false },
    yAxis: {
      type: 'category', data: items.map((item) => item.name),
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: chartInk.textMuted, fontSize: 9 },
    },
    series: [
      {
        name: '困难户构成', type: 'pie', radius: ['50%', '72%'], center: ['18%', '52%'],
        label: { show: false }, emphasis: { scale: false },
        data: items.map((item) => ({ value: item.value, name: item.name, itemStyle: { color: item.color } })),
      },
      {
        type: 'bar', barWidth: 11, showBackground: true,
        backgroundStyle: { color: chartInk.borderSoft, borderRadius: 3 },
        data: items.map((item) => ({ value: item.value, itemStyle: { color: item.color, borderRadius: 3 } })),
        label: {
          show: true, position: 'right', color: chartInk.textPrimary,
          fontFamily: 'monospace', fontSize: 9, formatter: '{c} 家',
        },
      },
    ],
  }
}
