/**
 * Canvas/ECharts 无法可靠消费 Tailwind 的 CSS 自定义属性，因此图表排版使用
 * 这一组类型安全的语义 Token。数值与 theme.css 的驾驶舱字号阶梯保持对应；
 * 只有 Canvas 特有的高密度字号保留为 chart-only token。
 */
export const CHART_FONT = {
  micro: 11,
  axis: 12,
  caption: 13,
  body: 14,
  tooltip: 15,
  subMetric: 16,
  metric: 19,
  kpi: 26,
} as const
