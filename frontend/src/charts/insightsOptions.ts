import type { EChartsOption } from 'echarts'
import type { RiskDimensionSummary } from '../utils/qualityMetrics'
import { calmAnimation, chartInk, chartPalette, chartTooltip, valueAxis } from './theme'
import { CHART_FONT } from './tokens'

export interface ModelQualityData {
  quality: number | null
  target: string
  ready: boolean
}

const riskToneColors = {
  danger: chartPalette.danger,
  warning: chartPalette.warning,
  accent: chartPalette.accent,
} as const

export function createRiskDimensionOption(items: RiskDimensionSummary[], total: number) {
  const list = [...items].reverse()

  return {
    ...calmAnimation,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      ...chartTooltip,
      formatter: (params: any) => {
        const point = Array.isArray(params) ? params[0] : params
        const raw = list[point?.dataIndex]
        if (!raw) return ''
        const percent = total > 0 ? ((raw.count / total) * 100).toFixed(1) : '0.0'
        const batchKeys = Object.keys(raw.batchDistribution)
        const batchDetails = batchKeys.length
          ? batchKeys.map((key) => `${key} (${raw.batchDistribution[key]}家)`).join('、')
          : '暂无集中批次'

        return `
          <div style="font-size: 12px; line-height: 1.6;">
            <div style="font-weight: 600; color: ${chartInk.textPrimary}; margin-bottom: 4px;">${raw.type} · 高危 ${raw.highCount} / 关注 ${raw.count - raw.highCount}</div>
            <div style="color: ${chartInk.textMuted};">预警规模: <b style="color: ${chartInk.textPrimary}; font-family: monospace;">${raw.count} 家</b> (${percent}%)</div>
            <div style="color: ${chartInk.textMuted};">集中批次: <span style="color: ${chartInk.textPrimary};">${batchDetails}</span></div>
            <div style="color: ${chartInk.textMuted}; margin-top: 4px; border-top: 1px dashed ${chartInk.borderSoft}; padding-top: 4px;">门禁规则: ${raw.gate}</div>
          </div>
        `
      },
    },
    grid: { top: 10, bottom: 4, left: 80, right: 60, containLabel: true },
    xAxis: {
      ...valueAxis,
      minInterval: 1,
      axisLabel: { show: false },
      splitLine: { lineStyle: { color: chartInk.borderSoft, type: 'dashed' } },
    },
    yAxis: {
      type: 'category',
      data: list.map((item) => item.type),
      axisLabel: { color: chartInk.textMuted, fontSize: CHART_FONT.caption },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: chartInk.border } },
    },
    series: [{
      name: '单位数量',
      type: 'bar',
      barWidth: 12,
      data: list.map((item) => ({
        value: item.count,
        itemStyle: { borderRadius: [0, 4, 4, 0], color: riskToneColors[item.tone] },
      })),
      label: {
        show: true,
        position: 'right',
        color: chartInk.textPrimary,
        fontFamily: 'monospace',
        fontSize: CHART_FONT.caption,
        fontWeight: 'bold',
        formatter: '{c} 家',
      },
      showBackground: true,
      backgroundStyle: { color: chartInk.borderSoft, borderRadius: [0, 4, 4, 0] },
    }],
  } satisfies EChartsOption
}

export function createModelQualityOption(data: ModelQualityData) {
  const qualityPercent = data.quality == null ? 0 : Math.max(0, Math.min(100, data.quality * 100))
  const qualityLabel = data.quality == null
    ? '—'
    : (data.target.includes('daily')
        ? `R² ${data.quality.toFixed(4)}`
        : `Acc ${(data.quality * 100).toFixed(1)}%`)

  return {
    ...calmAnimation,
    series: [{
      type: 'gauge',
      startAngle: 90,
      endAngle: -270,
      radius: '84%',
      center: ['50%', '50%'],
      silent: true,
      pointer: { show: false },
      progress: {
        show: data.quality != null,
        roundCap: true,
        width: 8,
        itemStyle: { color: data.ready ? chartPalette.success : chartPalette.warning },
      },
      axisLine: { lineStyle: { width: 8, color: [[1, chartInk.border]] } },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      title: { show: true, offsetCenter: [0, '35%'], color: chartInk.textMuted, fontSize: CHART_FONT.micro },
      detail: {
        offsetCenter: [0, '-6%'],
        color: chartInk.textPrimary,
        fontFamily: 'monospace',
        fontSize: CHART_FONT.subMetric,
        formatter: qualityLabel,
      },
      data: [{ value: qualityPercent, name: '测试集拟合' }],
    }],
  } satisfies EChartsOption
}
