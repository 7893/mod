import type { EChartsOption } from 'echarts'
import { formatCount } from '../formatters/metrics'
import { calmAnimation, chartInk, chartPalette, chartTooltip } from './theme'
import { CHART_FONT } from './tokens'

export interface ProgressRingsInput {
  constructionProgress: number
  rolloutRate: number
}

export interface OperationsVolumeInput {
  documents: number
  vouchers: number
  integrations: number
}

export interface RiskClosureInput {
  resolved: number
  unresolved: number
}

export function createProgressRingsOption(input: ProgressRingsInput) {
  return {
    ...calmAnimation,
    tooltip: { trigger: 'item', ...chartTooltip, formatter: '{b}<br/><b>{c}%</b>' },
    series: [
      {
        name: '建设进度', type: 'pie', radius: ['70%', '88%'], center: ['50%', '50%'],
        silent: false, label: { show: false }, emphasis: { scale: false },
        data: [
          { value: input.constructionProgress, name: '建设完成', itemStyle: { color: chartPalette.accent } },
          { value: 100 - input.constructionProgress, name: '建设待完成', itemStyle: { color: chartInk.borderSoft } },
        ],
      },
      {
        name: '推广上线', type: 'pie', radius: ['43%', '59%'], center: ['50%', '50%'],
        silent: false, label: { show: false }, emphasis: { scale: false },
        data: [
          { value: input.rolloutRate, name: '已上线', itemStyle: { color: chartPalette.success } },
          { value: 100 - input.rolloutRate, name: '待上线', itemStyle: { color: chartInk.borderSoft } },
        ],
      },
    ],
  } satisfies EChartsOption
}

export function createOperationsVolumeOption(input: OperationsVolumeInput) {
  const items = [
    { name: '业务单据', value: input.documents, color: chartPalette.accent },
    { name: '会计凭证', value: input.vouchers, color: chartPalette.success },
    { name: '接口集成', value: input.integrations, color: chartPalette.warning },
  ].reverse()

  return {
    ...calmAnimation,
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...chartTooltip },
    grid: { left: 62, right: 76, top: 2, bottom: 2 },
    xAxis: { type: 'value', show: false },
    yAxis: {
      type: 'category', data: items.map((item) => item.name),
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: chartInk.textMuted, fontSize: CHART_FONT.micro },
    },
    series: [{
      type: 'bar', barWidth: 8, showBackground: true,
      backgroundStyle: { color: chartInk.borderSoft, borderRadius: 3 },
      data: items.map((item) => ({ value: item.value, itemStyle: { color: item.color, borderRadius: 3 } })),
      label: {
        show: true, position: 'right', color: chartInk.textPrimary, fontFamily: 'monospace', fontSize: CHART_FONT.micro,
        formatter: (params: any) => formatCount(params.value),
      },
    }],
  } satisfies EChartsOption
}

export function createRiskClosureOption(input: RiskClosureInput) {
  return {
    ...calmAnimation,
    tooltip: { trigger: 'item', ...chartTooltip },
    series: [{
      name: '问题闭环',
      type: 'pie',
      radius: ['60%', '80%'],
      center: ['50%', '50%'],
      label: { show: false },
      data: [
        { value: input.resolved, name: '已闭环', itemStyle: { color: chartPalette.success } },
        { value: input.unresolved, name: '未解决', itemStyle: { color: chartPalette.danger } },
      ],
    }],
  } satisfies EChartsOption
}
