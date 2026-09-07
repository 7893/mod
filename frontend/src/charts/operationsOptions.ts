import { parsePercentage } from './panelData'
import { calmAnimation, chartInk, chartPalette, chartTooltip } from './theme'

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
