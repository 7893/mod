import { formatCount } from '../formatters/metrics'
import {
  calmAnimation,
  categoryAxis,
  chartInk,
  chartPalette,
  chartTooltip,
  valueAxis,
} from './theme'
import { parsePercentage, type CompositionTone } from './panelData'

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
  complianceRate: number | null
  highCount: number
}

interface BatchProgressItem {
  name: string
  construction: number
  launched: number
}

interface QualityRateItem {
  name: string
  value: number | null
  detail: string
  tone: 'accent' | 'success'
}

interface OperationalGuardItem {
  name: string
  value: number | null
  tone: 'danger' | 'warning' | 'accent'
}

interface CompositionPart {
  label: string
  value: number
  percentage: number
  tone: CompositionTone
}

const compositionColors: Record<CompositionTone, string> = {
  accent: chartPalette.accent,
  success: chartPalette.success,
  warning: chartPalette.warning,
  danger: chartPalette.danger,
  neutral: chartPalette.neutral,
}

export function createOverviewCompositionOption(parts: CompositionPart[], total: number) {
  return {
    ...calmAnimation,
    tooltip: {
      trigger: 'item',
      ...chartTooltip,
      formatter: (params: any) => {
        const part = parts[params?.seriesIndex]
        if (!part) return ''
        return `${part.label}<br/><b>${formatCount(part.value)}</b> · ${part.percentage}%`
      },
    },
    grid: { left: 0, right: 0, top: 0, bottom: 0 },
    xAxis: { type: 'value', max: total || 1, show: false },
    yAxis: { type: 'category', data: ['总体'], show: false },
    series: parts.map((part) => ({
      name: part.label,
      type: 'bar',
      stack: 'overview',
      barWidth: 18,
      silent: part.value === 0,
      data: [part.value],
      itemStyle: { color: compositionColors[part.tone] },
      label: {
        show: part.percentage >= 12,
        position: 'inside',
        color: chartInk.textPrimary,
        fontFamily: 'monospace',
        fontSize: 10,
        formatter: `${part.percentage}%`,
      },
    })),
  }
}

export function createRolloutCompositionOption(list: RolloutSeriesItem[]) {
  return {
    ...calmAnimation,
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...chartTooltip },
    grid: { left: 8, right: 12, top: 6, bottom: 6, containLabel: true },
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
    tooltip: {
      trigger: 'item',
      ...chartTooltip,
      formatter: (params: any) => {
        if (!coverage) return '暂无数据'
        const val = params.value != null ? formatCount(params.value) : ''
        return `单位覆盖率 <b>${coverage.rate}%</b><br/>${params.name}: <b>${val}</b> (${params.percent}%)`
      },
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

export function createProvinceProfileOption(progress?: number | string | null) {
  const parsedProgress = parsePercentage(progress)
  const hasValue = parsedProgress !== null
  const safeProgress = parsedProgress ?? 0
  return {
    ...calmAnimation,
    tooltip: { show: false },
    series: [{
      type: 'gauge',
      startAngle: 90,
      endAngle: -270,
      radius: '86%',
      center: ['50%', '50%'],
      silent: true,
      pointer: { show: false },
      progress: {
        show: hasValue,
        roundCap: true,
        width: 8,
        itemStyle: { color: chartPalette.accent },
      },
      axisLine: { lineStyle: { width: 8, color: [[1, chartInk.border]] } },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      title: { show: false },
      detail: { show: false },
      data: [{ value: safeProgress, name: '建设完成率' }],
    }],
  }
}

export function createBatchProgressOption(list: BatchProgressItem[]) {
  const reversed = [...list].reverse()
  return {
    ...calmAnimation,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any[]) => {
        const item = reversed[params?.[0]?.dataIndex]
        if (!item) return ''
        return `${item.name}<br/>建设完成度 <b>${item.construction}%</b><br/>上线率 <b>${item.launched}%</b>`
      },
      ...chartTooltip,
    },
    grid: { left: 6, right: 8, top: 4, bottom: 2, containLabel: true },
    xAxis: {
      ...valueAxis,
      min: 0,
      max: 100,
      splitNumber: 2,
      axisLabel: { color: chartInk.textMuted, fontSize: 9, formatter: '{value}%' },
    },
    yAxis: {
      type: 'category',
      data: reversed.map((batch) => batch.name),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: chartInk.border } },
      axisLabel: { color: chartInk.textMuted, fontSize: 10, interval: 0 },
    },
    // 建设完成度（单位进度均值）与上线率（单位数占比）分母不同，不能堆叠在同一根条里，只能并列。
    series: [
      {
        name: '建设完成度', type: 'bar', barGap: '10%', barMaxWidth: 8,
        data: reversed.map((batch) => batch.construction),
        itemStyle: { color: chartPalette.accent, borderRadius: [0, 3, 3, 0] },
        showBackground: true,
        backgroundStyle: { color: chartInk.borderSoft },
      },
      {
        name: '上线率', type: 'bar', barMaxWidth: 8,
        data: reversed.map((batch) => batch.launched),
        itemStyle: { color: chartPalette.success, borderRadius: [0, 3, 3, 0] },
        showBackground: true,
        backgroundStyle: { color: chartInk.borderSoft },
      },
    ],
  }
}

export function createOperationsQualityOption(list: QualityRateItem[]) {
  const reversed = [...list].reverse()
  return {
    ...calmAnimation,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any[]) => {
        const item = reversed[params?.[0]?.dataIndex]
        if (!item) return ''
        const value = item.value === null ? '—' : `${item.value}%`
        return `${item.name}<br/><b>${value}</b> · ${item.detail}`
      },
      ...chartTooltip,
    },
    grid: { left: 2, right: 42, top: 3, bottom: 3, containLabel: true },
    xAxis: { type: 'value', min: 0, max: 100, show: false },
    yAxis: {
      type: 'category',
      data: reversed.map((item) => item.name),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: chartInk.textMuted, fontSize: 10 },
    },
    series: [{
      type: 'bar',
      barWidth: 10,
      showBackground: true,
      backgroundStyle: { color: chartInk.borderSoft, borderRadius: 4 },
      data: reversed.map((item) => ({
        value: item.value ?? 0,
        itemStyle: {
          color: item.tone === 'success' ? chartPalette.success : chartPalette.accent,
          borderRadius: 4,
        },
      })),
      label: {
        show: true,
        position: 'right',
        color: chartInk.textPrimary,
        fontFamily: 'monospace',
        fontSize: 10,
        formatter: (params: any) => {
          const item = reversed[params?.dataIndex]
          return item?.value === null ? '—' : `${item?.value}%`
        },
      },
    }],
  }
}

export function createOperationalGuardOption(list: OperationalGuardItem[]) {
  const colors = {
    danger: chartPalette.danger,
    warning: chartPalette.warning,
    accent: chartPalette.accent,
  }
  const reversed = [...list].reverse()
  const max = Math.max(1, ...reversed.map((item) => item.value ?? 0))
  return {
    ...calmAnimation,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any[]) => {
        const item = reversed[params?.[0]?.dataIndex]
        return item ? `${item.name}<br/><b>${formatCount(item.value)}</b> 项` : ''
      },
      ...chartTooltip,
    },
    grid: { left: 4, right: 38, top: 2, bottom: 2, containLabel: true },
    xAxis: { type: 'value', max, show: false },
    yAxis: {
      type: 'category', data: reversed.map((item) => item.name),
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: chartInk.textMuted, fontSize: 9 },
    },
    series: [{
      type: 'bar', barWidth: 8, showBackground: true,
      backgroundStyle: { color: chartInk.borderSoft, borderRadius: 4 },
      data: reversed.map((item) => ({
        value: item.value ?? 0,
        itemStyle: { color: colors[item.tone], borderRadius: 4 },
      })),
      label: {
        show: true, position: 'right', color: chartInk.textPrimary,
        fontFamily: 'monospace', fontSize: 9,
        formatter: (params: any) => {
          const item = reversed[params?.dataIndex]
          return formatCount(item?.value)
        },
      },
    }],
  }
}

export function createBatchComplianceOption(list: ComplianceSeriesItem[]) {
  return {
    ...calmAnimation,
    tooltip: { trigger: 'axis', ...chartTooltip },
    grid: { left: 8, right: 8, top: 6, bottom: 6, containLabel: true },
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
        name: '高风险', type: 'bar', yAxisIndex: 1, barMaxWidth: 34,
        data: list.map((batch) => batch.highCount),
        itemStyle: { color: chartPalette.danger, borderRadius: [3, 3, 0, 0] },
      },
      {
        name: '合规率', type: 'line',
        data: list.map((batch) => batch.complianceRate),
        symbolSize: 5,
        lineStyle: { color: chartPalette.success, width: 2 },
        itemStyle: { color: chartPalette.success },
      },
    ],
  }
}
