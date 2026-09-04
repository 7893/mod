/**
 * 图表主题：与 styles/foundation.css 的设计令牌保持同一套色值。
 *
 * 各视图不得再自行定义 chartColors 局部色板，否则图表区与页面外壳会出现
 * 两套不同的蓝绿黄，导致整屏观感发灰、发脏。
 */

export const chartPalette = {
  accent: '#38bdf8',
  accentDim: '#0284c7',
  success: '#34d399',
  warning: '#fbbf24',
  danger: '#f43f5e',
  gold: '#fbbf24',
  neutral: '#64748b',
} as const

export const chartInk = {
  bgTooltip: 'rgba(8, 12, 20, 0.96)',
  border: 'rgba(255, 255, 255, 0.1)',
  borderSoft: 'rgba(255, 255, 255, 0.05)',
  textPrimary: '#f8fafc',
  textMuted: '#94a3b8',
} as const

/** 分类型数据的固定取色顺序，保证同一语义在各页面颜色一致。 */
export const chartSeriesColors = [
  chartPalette.accent,
  chartPalette.success,
  chartPalette.gold,
  chartPalette.warning,
  chartPalette.danger,
  chartPalette.neutral,
] as const

const axisLabel = { color: chartInk.textMuted, fontSize: 11 }

/** 统一 tooltip：深底、细边、无花哨阴影。 */
export const chartTooltip = {
  backgroundColor: chartInk.bgTooltip,
  borderColor: chartInk.border,
  borderWidth: 1,
  padding: [8, 12] as [number, number],
  textStyle: { color: chartInk.textPrimary, fontSize: 12 },
}

/** 类目轴统一样式。 */
export const categoryAxis = {
  type: 'category' as const,
  axisLine: { lineStyle: { color: chartInk.border } },
  axisTick: { show: false },
  axisLabel,
}

/** 数值轴统一样式：仅保留淡分割线，去掉轴线降低噪音。 */
export const valueAxis = {
  type: 'value' as const,
  axisLine: { show: false },
  axisTick: { show: false },
  splitLine: { lineStyle: { color: chartInk.borderSoft } },
  axisLabel,
}

/** 紧凑网格：大屏面板内图表统一留白，避免各页面各写一套。 */
export const compactGrid = {
  left: 8,
  right: 12,
  top: 16,
  bottom: 8,
  containLabel: true,
}

/**
 * 图表动效基线：仅保留一次性入场过渡，不做逐项延迟飞入。
 * 大屏长时间展示时，重复的强动效是视觉噪音而非信息。
 */
export const calmAnimation = {
  animation: true,
  animationDuration: 600,
  animationEasing: 'cubicOut' as const,
}
