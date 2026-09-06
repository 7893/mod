import {
  calmAnimation,
  categoryAxis,
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

interface RolloutSeriesItem {
  name: string
  launched: number
  dual: number
  pending: number
}

interface CoverageSeriesItem {
  covered: number
  gap: number
  rate: number
}

interface ComplianceSeriesItem {
  name: string
  complianceRate: string
  problemCount: number
  highCount: number
}

const compactLegend = (data: string[]) => ({
  data,
  top: 0,
  right: 8,
  textStyle: { color: chartInk.textMuted, fontSize: 10 },
  itemWidth: 10,
  itemHeight: 8,
})

export function createTaskStageOption(list: StageSeriesItem[]) {
  return {
    ...calmAnimation,
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...chartTooltip },
    legend: compactLegend(['已完成', '进行中', '未开始']),
    grid: { top: 24, right: 58, bottom: 8, left: 8, containLabel: true },
    xAxis: { ...valueAxis, axisLabel: { color: chartInk.textMuted, fontSize: 10 } },
    yAxis: {
      type: 'category',
      data: list.map((stage) => stage.name).reverse(),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: chartInk.border } },
      axisLabel: { color: chartInk.textMuted, fontSize: 11 },
    },
    series: [
      {
        name: '已完成', type: 'bar', stack: 'tasks', barMaxWidth: 14,
        data: list.map((stage) => stage.completed).reverse(),
        itemStyle: { color: chartPalette.success },
      },
      {
        name: '进行中', type: 'bar', stack: 'tasks',
        data: list.map((stage) => stage.inProgress).reverse(),
        itemStyle: { color: chartPalette.accent },
      },
      {
        name: '未开始', type: 'bar', stack: 'tasks',
        data: list.map((stage) => stage.notStarted).reverse(),
        itemStyle: { color: chartPalette.neutral },
        label: {
          show: true,
          position: 'right',
          color: chartInk.textMuted,
          fontFamily: 'monospace',
          fontSize: 10,
          formatter: (params: any) => `${list[list.length - 1 - params.dataIndex]?.progress ?? 0}%`,
        },
      },
    ],
  }
}

export function createRolloutCompositionOption(list: RolloutSeriesItem[]) {
  return {
    ...calmAnimation,
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...chartTooltip },
    legend: compactLegend(['已上线', '双轨', '待推进']),
    grid: { left: 8, right: 12, top: 24, bottom: 6, containLabel: true },
    xAxis: {
      type: 'category',
      data: list.map((batch) => batch.name),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: chartInk.border } },
      axisLabel: { color: chartInk.textMuted, fontSize: 10 },
    },
    yAxis: { ...valueAxis, axisLabel: { color: chartInk.textMuted, fontSize: 10 } },
    series: [
      {
        name: '已上线', type: 'bar', stack: 'units', barMaxWidth: 36,
        data: list.map((batch) => batch.launched), itemStyle: { color: chartPalette.success },
      },
      {
        name: '双轨', type: 'bar', stack: 'units',
        data: list.map((batch) => batch.dual), itemStyle: { color: chartPalette.warning },
      },
      {
        name: '待推进', type: 'bar', stack: 'units',
        data: list.map((batch) => batch.pending),
        itemStyle: { color: chartPalette.neutral, borderRadius: [3, 3, 0, 0] },
      },
    ],
  }
}

export function createCoverageOption(coverage: CoverageSeriesItem | null) {
  return {
    ...calmAnimation,
    tooltip: { trigger: 'item', ...chartTooltip },
    title: {
      text: coverage ? `${coverage.rate}%` : '—',
      subtext: '单位覆盖率',
      left: 'center',
      top: '36%',
      textStyle: { color: chartInk.textPrimary, fontSize: 18, fontFamily: 'monospace' },
      subtextStyle: { color: chartInk.textMuted, fontSize: 10 },
    },
    series: [{
      name: '联系人覆盖',
      type: 'pie',
      radius: ['58%', '78%'],
      center: ['50%', '50%'],
      silent: !coverage,
      label: { show: false },
      data: coverage
        ? [
            { value: coverage.covered, name: '已覆盖单位', itemStyle: { color: chartPalette.success } },
            { value: coverage.gap, name: '待补齐单位', itemStyle: { color: chartPalette.neutral } },
          ]
        : [{ value: 1, name: '暂无数据', itemStyle: { color: chartInk.borderSoft } }],
    }],
  }
}

export function createBatchComplianceOption(list: ComplianceSeriesItem[]) {
  return {
    ...calmAnimation,
    tooltip: { trigger: 'axis', ...chartTooltip },
    legend: compactLegend(['合规率', '重点监督', '高风险']),
    grid: { left: 8, right: 8, top: 24, bottom: 6, containLabel: true },
    xAxis: {
      ...categoryAxis,
      data: list.map((batch) => batch.name),
      axisLabel: { ...categoryAxis.axisLabel, fontSize: 10 },
    },
    yAxis: [
      {
        ...valueAxis, min: 0, max: 100,
        axisLabel: { color: chartInk.textMuted, fontSize: 10, formatter: '{value}%' },
      },
      { ...valueAxis, splitLine: { show: false }, axisLabel: { color: chartInk.textMuted, fontSize: 10 } },
    ],
    series: [
      {
        name: '重点监督', type: 'bar', yAxisIndex: 1, barMaxWidth: 30,
        data: list.map((batch) => batch.problemCount),
        itemStyle: { color: chartPalette.warning, opacity: 0.42, borderRadius: [3, 3, 0, 0] },
      },
      {
        name: '高风险', type: 'bar', yAxisIndex: 1, barMaxWidth: 30,
        data: list.map((batch) => batch.highCount),
        itemStyle: { color: chartPalette.danger, borderRadius: [3, 3, 0, 0] },
      },
      {
        name: '合规率', type: 'line',
        data: list.map((batch) => Number(batch.complianceRate)),
        symbolSize: 5,
        lineStyle: { color: chartPalette.success, width: 2 },
        itemStyle: { color: chartPalette.success },
      },
    ],
  }
}
