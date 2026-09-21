import type { EChartsOption } from 'echarts'
import { formatCount } from '../formatters/metrics'
import {
  calmAnimation,
  chartInk,
  chartPalette,
  chartTooltip,
  valueAxis,
} from './theme'
import { CHART_FONT } from './tokens'

interface StageSeriesItem {
  name: string
  completed: number
  inProgress: number
  notStarted: number
  progress: number
}

interface TrainingTypeItem {
  type: string
  count: number
  expected: number
  actual: number
  passed: number
  cert: number
}

interface TrainingSummaryItem {
  totalExpected: number
  totalActual: number
  totalPassed: number
  totalCert: number
}

interface ReadinessSummaryItem {
  imported?: number | null
  verified?: number | null
  collecting?: number | null
  notCollected?: number | null
}

export type GateStageItem = StageSeriesItem

export function createLaunchGateOption(items: GateStageItem[]) {
  const reversed = [...items].reverse()
  return {
    ...calmAnimation,
    tooltip: {
      trigger: 'axis', axisPointer: { type: 'shadow' }, ...chartTooltip,
      formatter: (params: any) => {
        const item = reversed[params?.[0]?.dataIndex]
        return item
          ? `${item.name}<br/>完成 <b>${formatCount(item.completed)}</b> · 进行中 ${formatCount(item.inProgress)} · 待启动 ${formatCount(item.notStarted)}<br/>总体完成率 <b>${item.progress}%</b>`
          : ''
      },
    },
    grid: { left: 58, right: 42, top: 8, bottom: 10 },
    xAxis: { type: 'value', max: 100, show: false },
    yAxis: {
      type: 'category', data: reversed.map((item) => item.name),
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: chartInk.textMuted, fontSize: CHART_FONT.caption },
    },
    series: [
      {
        name: '已完成', type: 'bar', stack: 'gate', barWidth: 13,
        data: reversed.map((item) => percent(item.completed, item.completed + item.inProgress + item.notStarted)),
        itemStyle: { color: chartPalette.success, borderRadius: [3, 0, 0, 3] },
      },
      {
        name: '进行中', type: 'bar', stack: 'gate',
        data: reversed.map((item) => percent(item.inProgress, item.completed + item.inProgress + item.notStarted)),
        itemStyle: { color: chartPalette.accent },
      },
      {
        name: '待启动', type: 'bar', stack: 'gate',
        data: reversed.map((item) => percent(item.notStarted, item.completed + item.inProgress + item.notStarted)),
        itemStyle: { color: chartPalette.neutral, borderRadius: [0, 3, 3, 0] },
        label: {
          show: true, position: 'right', color: chartInk.textPrimary,
          fontFamily: 'monospace', fontSize: CHART_FONT.axis,
          formatter: (params: any) => `${reversed[params.dataIndex]?.progress ?? 0}%`,
        },
      },
    ],
  } satisfies EChartsOption
}

const percent = (value: number, total: number) => (
  total > 0 ? Math.round((value * 1000) / total) / 10 : 0
)

export function createTaskStageMatrixOption(list: StageSeriesItem[]) {
  const statuses = [
    { name: '已完成', field: 'completed' as const, color: chartPalette.success },
    { name: '进行中', field: 'inProgress' as const, color: chartPalette.accent },
    { name: '未开始', field: 'notStarted' as const, color: chartPalette.neutral },
  ]
  const matrix = statuses.flatMap((status, rowIndex) => list.map((stage, columnIndex) => {
    const total = stage.completed + stage.inProgress + stage.notStarted
    const count = stage[status.field]
    return {
      value: [columnIndex, rowIndex, count],
      percentage: percent(count, total),
      itemStyle: { color: status.color, opacity: status.field === 'notStarted' ? 0.72 : 0.88 },
    }
  }))
  const maxCount = Math.max(1, ...matrix.map((item) => Number(item.value[2])))

  return {
    ...calmAnimation,
    tooltip: {
      trigger: 'item',
      ...chartTooltip,
      formatter: (params: any) => {
        const [columnIndex, rowIndex, count] = params.value ?? []
        const stage = list[columnIndex]
        const status = statuses[rowIndex]
        return stage && status
          ? `${stage.name} · ${status.name}<br/><b>${formatCount(count)}</b> 项 · ${params.data.percentage}%`
          : ''
      },
    },
    visualMap: {
      show: false,
      min: 0,
      max: maxCount,
      dimension: 2,
      seriesIndex: 0,
      inRange: { opacity: [0.7, 0.96] },
    },
    grid: { left: 58, right: 8, top: 10, bottom: 34 },
    xAxis: {
      type: 'category', data: list.map((stage) => stage.name),
      axisLine: { lineStyle: { color: chartInk.border } }, axisTick: { show: false },
      axisLabel: { color: chartInk.textMuted, fontSize: CHART_FONT.axis, interval: 0 },
    },
    yAxis: {
      type: 'category', data: statuses.map((status) => status.name),
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: chartInk.textMuted, fontSize: CHART_FONT.caption },
    },
    series: [{
      type: 'heatmap', data: matrix,
      label: {
        show: true, color: chartInk.textPrimary, fontFamily: 'monospace', fontSize: CHART_FONT.body,
        formatter: (params: any) => `${params.data.percentage}%\n${formatCount(params.value?.[2] ?? 0)}`,
      },
      itemStyle: { borderColor: chartInk.bgTooltip, borderWidth: 3, borderRadius: 4 },
      emphasis: { itemStyle: { borderColor: chartInk.textPrimary, borderWidth: 1 } },
    }],
  } satisfies EChartsOption
}

const shortTrainingType = (value: string) => value
  .replace('培训', '')
  .replace('与', ' / ')

export function createTrainingConversionOption(items: TrainingTypeItem[]) {
  return {
    ...calmAnimation,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      ...chartTooltip,
      formatter: (params: any) => {
        const item = items[params?.[0]?.dataIndex]
        if (!item) return ''
        const rate = item.actual > 0 ? percent(item.passed, item.actual) : 0
        return `${item.type}<br/>培训场次 <b>${formatCount(item.count)}</b><br/>实到 / 应到 <b>${formatCount(item.actual)} / ${formatCount(item.expected)}</b><br/>考核通过 <b>${formatCount(item.passed)}</b> · ${rate}%`
      },
    },
    grid: { left: 42, right: 12, top: 8, bottom: 38 },
    xAxis: {
      type: 'category',
      data: items.map((item) => shortTrainingType(item.type)),
      axisLine: { lineStyle: { color: chartInk.border } },
      axisTick: { show: false },
      axisLabel: { color: chartInk.textMuted, fontSize: CHART_FONT.axis, interval: 0 },
    },
    yAxis: {
      ...valueAxis,
      splitNumber: 3,
      axisLabel: {
        color: chartInk.textMuted,
        fontSize: CHART_FONT.axis,
        formatter: (value: number) => value >= 10_000 ? `${Math.round(value / 1000)}k` : String(value),
      },
    },
    series: [
      { name: '应到', type: 'bar', barMaxWidth: 18, data: items.map((item) => item.expected), itemStyle: { color: chartPalette.neutral, borderRadius: [3, 3, 0, 0] } },
      { name: '实到', type: 'bar', barMaxWidth: 18, data: items.map((item) => item.actual), itemStyle: { color: chartPalette.accent, borderRadius: [3, 3, 0, 0] } },
      { name: '通过', type: 'bar', barMaxWidth: 18, data: items.map((item) => item.passed), itemStyle: { color: chartPalette.success, borderRadius: [3, 3, 0, 0] } },
      { name: '认证', type: 'bar', barMaxWidth: 18, data: items.map((item) => item.cert), itemStyle: { color: chartPalette.warning, borderRadius: [3, 3, 0, 0] } },
    ],
  } satisfies EChartsOption
}

export function createTrainingMixOption(items: TrainingTypeItem[]) {
  return {
    ...calmAnimation,
    tooltip: {
      trigger: 'item',
      ...chartTooltip,
      formatter: (params: any) => `${params.name}<br/>培训场次 <b>${formatCount(params.value)}</b> · ${params.percent}%`,
    },
    series: [{
      type: 'pie',
      radius: ['48%', '72%'],
      center: ['42%', '52%'],
      minAngle: 4,
      avoidLabelOverlap: true,
      itemStyle: { borderColor: chartInk.bgTooltip, borderWidth: 2 },
      label: { color: chartInk.textMuted, fontSize: CHART_FONT.axis, formatter: '{b}\n{d}%' },
      labelLine: { length: 6, length2: 4, lineStyle: { color: chartInk.border } },
      data: items.map((item, index) => ({
        name: shortTrainingType(item.type),
        value: item.count,
        itemStyle: {
          color: [chartPalette.accent, chartPalette.success, chartPalette.warning, chartPalette.neutral][index % 4],
        },
      })),
    }],
  } satisfies EChartsOption
}

export function createTrainingFunnelOption(summary?: TrainingSummaryItem) {
  const list = [
    { name: '应参培', value: summary?.totalExpected ?? 0, color: chartPalette.neutral },
    { name: '实参培', value: summary?.totalActual ?? 0, color: chartPalette.accent },
    { name: '考核通过', value: summary?.totalPassed ?? 0, color: chartPalette.success },
    { name: '证书发放', value: summary?.totalCert ?? 0, color: chartPalette.warning },
  ].reverse()

  return {
    ...calmAnimation,
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...chartTooltip },
    grid: { left: 66, right: 64, top: 8, bottom: 18 },
    xAxis: { type: 'value', show: false },
    yAxis: {
      type: 'category',
      data: list.map((item) => item.name),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: chartInk.textMuted, fontSize: CHART_FONT.caption },
    },
    series: [{
      type: 'bar',
      barWidth: 16,
      showBackground: true,
      backgroundStyle: { color: chartInk.borderSoft, borderRadius: 4 },
      data: list.map((item) => ({
        value: item.value,
        itemStyle: { color: item.color, borderRadius: 4 },
      })),
      label: {
        show: true,
        position: 'right',
        color: chartInk.textPrimary,
        fontFamily: 'monospace',
        fontSize: CHART_FONT.caption,
        formatter: (params: any) => formatCount(params.value),
      },
    }],
  } satisfies EChartsOption
}

export function createReadinessPieOption(summary?: ReadinessSummaryItem) {
  return {
    ...calmAnimation,
    tooltip: {
      trigger: 'item',
      ...chartTooltip,
    },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'center',
      textStyle: { color: chartInk.textMuted, fontSize: CHART_FONT.caption },
      itemWidth: 10,
      itemHeight: 10,
    },
    series: [{
      name: '数据准备度',
      type: 'pie',
      radius: ['45%', '70%'],
      center: ['35%', '50%'],
      data: [
        { value: summary?.imported ?? 0, name: '已导入', itemStyle: { color: chartPalette.accent } },
        { value: summary?.verified ?? 0, name: '已校验', itemStyle: { color: chartPalette.success } },
        { value: summary?.collecting ?? 0, name: '收集中', itemStyle: { color: chartPalette.warning } },
        { value: summary?.notCollected ?? 0, name: '未收集', itemStyle: { color: chartPalette.neutral } },
      ],
      label: { show: false },
    }],
  } satisfies EChartsOption
}
