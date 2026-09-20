import type { EChartsOption } from 'echarts'
import { formatCount } from '../formatters/metrics'
import {
  calmAnimation,
  categoryAxis,
  chartInk,
  chartPalette,
  chartSeriesColors,
  chartTooltip,
  compactGrid,
  valueAxis,
} from './theme'
import { CHART_FONT } from './tokens'

export interface ComplianceOverviewData {
  rate: number | null
  supervised: number
  high: number
  medium: number
}

export interface ComplianceTagCount {
  label: string
  count: number
}

export interface ComplianceRiskComposition {
  compliant: number
  medium: number
  high: number
}

const complianceTagColors: Record<string, string> = {
  超期挂账: chartSeriesColors[3],
  超预算迹象: chartSeriesColors[4],
  票据异常: chartSeriesColors[2],
  准备期卡顿: chartSeriesColors[1],
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
      axisLabel: { color: chartInk.textMuted, fontSize: CHART_FONT.axis },
    },
    series: [
      {
        type: 'gauge', startAngle: 210, endAngle: -30,
        center: ['14%', '54%'], radius: '82%', silent: true,
        pointer: { show: false },
        progress: { show: data.rate != null, roundCap: true, width: 9, itemStyle: { color: chartPalette.success } },
        axisLine: { lineStyle: { width: 9, color: [[1, chartInk.borderSoft]] } },
        axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false },
        title: { show: true, offsetCenter: [0, '42%'], color: chartInk.textMuted, fontSize: CHART_FONT.axis },
        detail: {
          offsetCenter: [0, '-6%'], color: chartInk.textPrimary,
          fontFamily: 'monospace', fontSize: CHART_FONT.metric,
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
          fontFamily: 'monospace', fontSize: CHART_FONT.axis, formatter: '{c} 家',
        },
      },
    ],
  } satisfies EChartsOption
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

export function createComplianceRiskOption(data: ComplianceRiskComposition) {
  return {
    ...calmAnimation,
    tooltip: { trigger: 'item', ...chartTooltip },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'center',
      textStyle: { color: chartInk.textMuted, fontSize: CHART_FONT.caption },
      itemWidth: 10,
      itemHeight: 10,
    },
    series: [{
      name: '合规水位构成',
      type: 'pie',
      radius: ['45%', '70%'],
      center: ['35%', '50%'],
      data: [
        { value: data.compliant, name: `合规达标 (${formatCount(data.compliant)})`, itemStyle: { color: chartPalette.success } },
        { value: data.medium, name: `中度瑕疵 (${formatCount(data.medium)})`, itemStyle: { color: chartPalette.warning } },
        { value: data.high, name: `高风险隐患 (${formatCount(data.high)})`, itemStyle: { color: chartPalette.danger } },
      ],
      label: { show: false },
    }],
  } satisfies EChartsOption
}
