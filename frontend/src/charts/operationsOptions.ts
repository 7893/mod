import { parsePercentage } from './panelData'
import { calmAnimation, chartInk, chartPalette, chartTooltip } from './theme'

export interface OperationsOverviewCounts {
  businessDocument?: number | null
  accountingVoucher?: number | null
  integrationResult?: number | null
  dualRunResult?: number | null
}

interface OutcomeItem {
  name: string
  value: number | null | undefined
  color: string
}

export interface OperationsTrendPoint {
  date: string
  documents: number | null
  vouchers: number | null
  integrations: number | null
  integrationSuccessPct: number | null
}

export interface QualityVolumeItem {
  rule: string
  total: number | null
  errors: number | null
  rate: number | null
  unit: string
}

function createHorizontalVolumeOption(items: OutcomeItem[]) {
  const safeItems = items.map((item) => ({ ...item, value: item.value ?? 0 }))
  const max = Math.max(1, ...safeItems.map((item) => item.value))
  return {
    ...calmAnimation,
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...chartTooltip },
    grid: { left: 68, right: 82, top: 8, bottom: 8 },
    xAxis: { type: 'value', max, show: false },
    yAxis: {
      type: 'category', data: safeItems.map((item) => item.name),
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: chartInk.textMuted, fontSize: 10 },
    },
    series: [{
      type: 'bar', barWidth: 12, showBackground: true,
      backgroundStyle: { color: chartInk.borderSoft, borderRadius: 4 },
      data: safeItems.map((item) => ({ value: item.value, itemStyle: { color: item.color, borderRadius: 4 } })),
      label: {
        show: true, position: 'right', color: chartInk.textPrimary,
        fontFamily: 'monospace', fontSize: 10,
        formatter: (params: any) => Number(params.value).toLocaleString(),
      },
    }],
  }
}

export function createOperationsOverviewOption(counts: OperationsOverviewCounts) {
  const items = [
    { name: '接口集成', value: counts.integrationResult ?? 0, color: chartPalette.warning },
    { name: '会计凭证', value: counts.accountingVoucher ?? 0, color: chartPalette.success },
    { name: '业务单据', value: counts.businessDocument ?? 0, color: chartPalette.accent },
  ]
  return {
    ...calmAnimation,
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...chartTooltip },
    grid: { left: 62, right: 82, top: 7, bottom: 7 },
    xAxis: { type: 'value', show: false },
    yAxis: {
      type: 'category', data: items.map((item) => item.name),
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: chartInk.textMuted, fontSize: 9 },
    },
    series: [{
      type: 'bar', barWidth: 11, showBackground: true,
      backgroundStyle: { color: chartInk.borderSoft, borderRadius: 3 },
      data: items.map((item) => ({ value: item.value, itemStyle: { color: item.color, borderRadius: 3 } })),
      label: {
        show: true, position: 'right', color: chartInk.textPrimary,
        fontFamily: 'monospace', fontSize: 9,
        formatter: (params: any) => Number(params.value).toLocaleString(),
      },
    }],
  }
}

export function createOperationsFlowOption(counts: OperationsOverviewCounts) {
  return createHorizontalVolumeOption([
    { name: '双轨核对', value: counts.dualRunResult, color: chartPalette.neutral },
    { name: '接口集成', value: counts.integrationResult, color: chartPalette.warning },
    { name: '会计凭证', value: counts.accountingVoucher, color: chartPalette.success },
    { name: '业务单据', value: counts.businessDocument, color: chartPalette.accent },
  ])
}

export function createOperationsTrendOption(points: OperationsTrendPoint[]) {
  return {
    ...calmAnimation,
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' }, ...chartTooltip },
    grid: { left: 46, right: 40, top: 8, bottom: 26 },
    xAxis: {
      type: 'category', data: points.map((point) => point.date),
      axisLine: { lineStyle: { color: chartInk.border } }, axisTick: { show: false },
      axisLabel: { color: chartInk.textMuted, fontSize: 9 },
    },
    yAxis: [
      { type: 'value', splitNumber: 3, axisLabel: { color: chartInk.textMuted, fontSize: 9 }, splitLine: { lineStyle: { color: chartInk.borderSoft } } },
      { type: 'value', min: 0, max: 100, axisLabel: { color: chartInk.textMuted, fontSize: 9, formatter: '{value}%' }, splitLine: { show: false } },
    ],
    series: [
      { name: '单据日增', type: 'bar', barMaxWidth: 16, data: points.map((point) => point.documents), itemStyle: { color: chartPalette.accent, borderRadius: [3, 3, 0, 0] } },
      { name: '凭证日增', type: 'bar', barMaxWidth: 16, data: points.map((point) => point.vouchers), itemStyle: { color: chartPalette.success, borderRadius: [3, 3, 0, 0] } },
      { name: '集成成功率', type: 'line', yAxisIndex: 1, data: points.map((point) => point.integrationSuccessPct), connectNulls: false, symbolSize: 5, lineStyle: { color: chartPalette.warning, width: 2 }, itemStyle: { color: chartPalette.warning } },
    ],
  }
}

export function createQualityAuditVolumeOption(items: QualityVolumeItem[]) {
  const reversed = [...items].reverse()
  const plotted = reversed.map((item) => item.total != null && item.total >= 0 ? Math.log10(item.total + 1) : 0)
  return {
    ...calmAnimation,
    tooltip: {
      trigger: 'axis', axisPointer: { type: 'shadow' }, ...chartTooltip,
      formatter: (params: any[]) => {
        const item = reversed[params?.[0]?.dataIndex]
        if (!item) return ''
        return `${item.rule}<br/>核验规模 <b>${item.total == null ? '—' : item.total.toLocaleString()} ${item.unit}</b><br/>检出异常 <b>${item.errors == null ? '—' : item.errors.toLocaleString()}</b> · 合规率 ${item.rate == null ? '—' : `${item.rate}%`}<br/><span style="color:${chartInk.textMuted}">柱长为对数尺度，仅比较数量级</span>`
      },
    },
    grid: { left: 78, right: 84, top: 8, bottom: 8 },
    xAxis: { type: 'value', show: false, max: Math.max(1, ...plotted) },
    yAxis: {
      type: 'category', data: reversed.map((item) => item.rule),
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: chartInk.textMuted, fontSize: 10 },
    },
    series: [{
      type: 'bar', barWidth: 14, showBackground: true,
      backgroundStyle: { color: chartInk.borderSoft, borderRadius: 4 },
      data: plotted.map((value, index) => {
        const item = reversed[index]
        const color = (item?.errors ?? 0) > 0
          ? chartPalette.warning
          : (item?.errors === 0 ? chartPalette.success : chartPalette.neutral)
        return {
          value,
          itemStyle: { color, borderRadius: 4 },
        }
      }),
      label: {
        show: true, position: 'right', color: chartInk.textPrimary,
        fontFamily: 'monospace', fontSize: 10,
        formatter: (params: any) => {
          const item = reversed[params.dataIndex]
          return item?.total == null ? '—' : item.total.toLocaleString()
        },
      },
    }],
  }
}

export function createIntegrationOutcomeOption(success?: number | null, failed?: number | null) {
  return createHorizontalVolumeOption([
    { name: '异常待核', value: failed, color: chartPalette.danger },
    { name: '成功入账', value: success, color: chartPalette.success },
  ])
}

export function createDualRunOutcomeOption(consistent?: number | null, inconsistent?: number | null) {
  return createHorizontalVolumeOption([
    { name: '差异待核', value: inconsistent, color: chartPalette.warning },
    { name: '核对一致', value: consistent, color: chartPalette.success },
  ])
}

export function createVoucherQualityOption(
  successRate: unknown,
  voucherCount?: number | null,
  lineCount?: number | null,
) {
  const parsedRate = parsePercentage(successRate)
  const hasRate = parsedRate !== null
  const safeRate = parsedRate ?? 0
  const volumes = [
    { name: '凭证主表', value: voucherCount ?? 0, color: chartPalette.accent },
    { name: '分录明细', value: lineCount ?? 0, color: chartPalette.success },
  ].reverse()

  return {
    ...calmAnimation,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      ...chartTooltip,
      formatter: (params: any[]) => {
        const item = volumes[params?.[0]?.dataIndex]
        return item ? `${item.name}<br/><b>${item.value.toLocaleString()}</b>` : ''
      },
    },
    grid: { left: '35%', right: 66, top: 16, bottom: 16, containLabel: true },
    xAxis: { type: 'value', show: false },
    yAxis: {
      type: 'category',
      data: volumes.map((item) => item.name),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: chartInk.textMuted, fontSize: 10 },
    },
    series: [
      {
        type: 'gauge',
        startAngle: 90,
        endAngle: -270,
        radius: '82%',
        center: ['16%', '50%'],
        silent: true,
        pointer: { show: false },
        progress: {
          show: hasRate,
          roundCap: true,
          width: 9,
          itemStyle: { color: chartPalette.success },
        },
        axisLine: { lineStyle: { width: 9, color: [[1, chartInk.border]] } },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        title: { show: true, offsetCenter: [0, '36%'], color: chartInk.textMuted, fontSize: 10 },
        detail: {
          valueAnimation: true,
          offsetCenter: [0, '-6%'],
          color: chartInk.textPrimary,
          fontFamily: 'monospace',
          fontSize: 17,
          formatter: hasRate ? '{value}%' : '—',
        },
        data: [{ value: safeRate, name: '生成成功率' }],
      },
      {
        type: 'bar',
        barWidth: 13,
        showBackground: true,
        backgroundStyle: { color: chartInk.borderSoft, borderRadius: 4 },
        data: volumes.map((item) => ({
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
      },
    ],
  }
}
