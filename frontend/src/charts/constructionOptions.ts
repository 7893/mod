import {
  calmAnimation,
  chartInk,
  chartPalette,
  chartTooltip,
  valueAxis,
} from './theme'

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

const compactLegend = (data: string[]) => ({
  data,
  top: 0,
  right: 8,
  textStyle: { color: chartInk.textMuted, fontSize: 10 },
  itemWidth: 10,
  itemHeight: 8,
})

const percent = (value: number, total: number) => (
  total > 0 ? Math.round((value * 1000) / total) / 10 : 0
)

export function createTaskStageOverviewOption(list: StageSeriesItem[]) {
  const stages = list.map((item) => {
    const total = item.completed + item.inProgress + item.notStarted
    return {
      ...item,
      completedPct: percent(item.completed, total),
      inProgressPct: percent(item.inProgress, total),
      notStartedPct: percent(item.notStarted, total),
    }
  })

  return {
    ...calmAnimation,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      ...chartTooltip,
      formatter: (params: any[]) => {
        const item = stages[params?.[0]?.dataIndex]
        if (!item) return ''
        return `${item.name}<br/>已完成 <b>${item.completed.toLocaleString()}</b><br/>进行中 <b>${item.inProgress.toLocaleString()}</b><br/>未开始 <b>${item.notStarted.toLocaleString()}</b><br/>阶段完成率 <b>${item.progress}%</b>`
      },
    },
    legend: compactLegend(['已完成', '进行中', '未开始']),
    grid: { left: 38, right: 14, top: 28, bottom: 32 },
    xAxis: {
      type: 'category',
      data: stages.map((item) => item.name),
      axisLine: { lineStyle: { color: chartInk.border } },
      axisTick: { show: false },
      axisLabel: { color: chartInk.textMuted, fontSize: 10, interval: 0 },
    },
    yAxis: {
      ...valueAxis,
      min: 0,
      max: 100,
      splitNumber: 2,
      axisLabel: { color: chartInk.textMuted, fontSize: 9, formatter: '{value}%' },
    },
    series: [
      {
        name: '已完成', type: 'bar', stack: 'stage', barMaxWidth: 42,
        data: stages.map((item) => item.completedPct),
        itemStyle: { color: chartPalette.success },
        label: {
          show: true,
          position: 'inside',
          color: chartInk.textPrimary,
          fontFamily: 'monospace',
          fontSize: 9,
          formatter: (params: any) => Number(params.value) >= 20 ? `${params.value}%` : '',
        },
      },
      {
        name: '进行中', type: 'bar', stack: 'stage',
        data: stages.map((item) => item.inProgressPct),
        itemStyle: { color: chartPalette.accent },
      },
      {
        name: '未开始', type: 'bar', stack: 'stage',
        data: stages.map((item) => item.notStartedPct),
        itemStyle: { color: chartPalette.neutral, borderRadius: [3, 3, 0, 0] },
      },
    ],
  }
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
      formatter: (params: any[]) => {
        const item = items[params?.[0]?.dataIndex]
        if (!item) return ''
        const rate = item.actual > 0 ? percent(item.passed, item.actual) : 0
        return `${item.type}<br/>培训场次 <b>${item.count.toLocaleString()}</b><br/>实到 / 应到 <b>${item.actual.toLocaleString()} / ${item.expected.toLocaleString()}</b><br/>考核通过 <b>${item.passed.toLocaleString()}</b> · ${rate}%`
      },
    },
    legend: {
      data: ['应到', '实到', '通过', '认证'],
      top: 2,
      right: 4,
      textStyle: { color: chartInk.textMuted, fontSize: 9 },
      itemWidth: 9,
      itemHeight: 7,
    },
    grid: { left: 42, right: 12, top: 30, bottom: 38 },
    xAxis: {
      type: 'category',
      data: items.map((item) => shortTrainingType(item.type)),
      axisLine: { lineStyle: { color: chartInk.border } },
      axisTick: { show: false },
      axisLabel: { color: chartInk.textMuted, fontSize: 9, interval: 0 },
    },
    yAxis: {
      ...valueAxis,
      splitNumber: 3,
      axisLabel: {
        color: chartInk.textMuted,
        fontSize: 9,
        formatter: (value: number) => value >= 10_000 ? `${Math.round(value / 1000)}k` : value,
      },
    },
    series: [
      { name: '应到', type: 'bar', barMaxWidth: 18, data: items.map((item) => item.expected), itemStyle: { color: chartPalette.neutral, borderRadius: [3, 3, 0, 0] } },
      { name: '实到', type: 'bar', barMaxWidth: 18, data: items.map((item) => item.actual), itemStyle: { color: chartPalette.accent, borderRadius: [3, 3, 0, 0] } },
      { name: '通过', type: 'bar', barMaxWidth: 18, data: items.map((item) => item.passed), itemStyle: { color: chartPalette.success, borderRadius: [3, 3, 0, 0] } },
      { name: '认证', type: 'bar', barMaxWidth: 18, data: items.map((item) => item.cert), itemStyle: { color: chartPalette.warning, borderRadius: [3, 3, 0, 0] } },
    ],
  }
}

export function createTrainingMixOption(items: TrainingTypeItem[]) {
  return {
    ...calmAnimation,
    tooltip: {
      trigger: 'item',
      ...chartTooltip,
      formatter: (params: any) => `${params.name}<br/>培训场次 <b>${Number(params.value).toLocaleString()}</b> · ${params.percent}%`,
    },
    series: [{
      type: 'pie',
      radius: ['48%', '72%'],
      center: ['42%', '52%'],
      minAngle: 4,
      avoidLabelOverlap: true,
      itemStyle: { borderColor: chartInk.bgTooltip, borderWidth: 2 },
      label: { color: chartInk.textMuted, fontSize: 9, formatter: '{b}\n{d}%' },
      labelLine: { length: 6, length2: 4, lineStyle: { color: chartInk.border } },
      data: items.map((item, index) => ({
        name: shortTrainingType(item.type),
        value: item.count,
        itemStyle: {
          color: [chartPalette.accent, chartPalette.success, chartPalette.warning, chartPalette.neutral][index % 4],
        },
      })),
    }],
  }
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
      axisLabel: { color: chartInk.textMuted, fontSize: 10 },
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
        fontSize: 10,
        formatter: (params: any) => Number(params.value).toLocaleString(),
      },
    }],
  }
}
