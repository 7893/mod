import type { EChartsOption } from 'echarts'
import {
  calmAnimation,
  categoryAxis,
  chartPalette,
  chartSeriesColors,
  chartTooltip,
  compactGrid,
  valueAxis,
} from './theme'
import { CHART_FONT } from './tokens'

export interface ComplianceTagCount {
  label: string
  count: number
}

const complianceTagColors: Record<string, string> = {
  超期挂账: chartSeriesColors[3],
  超预算迹象: chartSeriesColors[4],
  票据异常: chartSeriesColors[2],
  准备期卡顿: chartSeriesColors[1],
}

export function createComplianceTagOption(items: ComplianceTagCount[]) {
  return {
    ...calmAnimation,
    tooltip: { trigger: 'axis', ...chartTooltip },
    grid: { ...compactGrid, bottom: 18 },
    xAxis: {
      ...categoryAxis,
      data: items.map((item) => item.label),
      axisLabel: { ...categoryAxis.axisLabel, interval: 0, fontSize: CHART_FONT.axis },
    },
    yAxis: valueAxis,
    series: [{
      name: '涉及单位数',
      type: 'bar',
      data: items.map((item) => ({
        value: item.count,
        itemStyle: { color: complianceTagColors[item.label] ?? chartPalette.neutral },
      })),
      barWidth: '42%',
      barMaxWidth: 48,
      itemStyle: { borderRadius: [3, 3, 0, 0] },
    }],
  } satisfies EChartsOption
}
