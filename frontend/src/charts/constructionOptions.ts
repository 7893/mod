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

export function createTrainingPerformanceOption(items: TrainingTypeItem[]) {
  const list = [...items].reverse()
  return {
    ...calmAnimation,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      ...chartTooltip,
      formatter: (params: any[]) => {
        const item = list[params?.[0]?.dataIndex]
        if (!item) return ''
        const rate = item.actual > 0 ? percent(item.passed, item.actual) : 0
        return `${item.type}<br/>培训场次 <b>${item.count.toLocaleString()}</b><br/>实到 / 应到 <b>${item.actual.toLocaleString()} / ${item.expected.toLocaleString()}</b><br/>考核通过 <b>${item.passed.toLocaleString()}</b> · ${rate}%`
      },
    },
    grid: { left: 122, right: 48, top: 8, bottom: 18 },
    xAxis: {
      ...valueAxis,
      min: 0,
      max: 100,
      splitNumber: 2,
      axisLabel: { color: chartInk.textMuted, fontSize: 9, formatter: '{value}%' },
    },
    yAxis: {
      type: 'category',
      data: list.map((item) => shortTrainingType(item.type)),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: chartInk.textMuted, fontSize: 10 },
    },
    series: [{
      type: 'bar',
      barWidth: 16,
      showBackground: true,
      backgroundStyle: { color: chartInk.borderSoft, borderRadius: 4 },
      data: list.map((item) => item.actual > 0 ? percent(item.passed, item.actual) : 0),
      itemStyle: { color: chartPalette.accent, borderRadius: 4 },
      label: {
        show: true,
        position: 'right',
        color: chartPalette.success,
        fontFamily: 'monospace',
        fontSize: 10,
        formatter: '{c}%',
      },
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
