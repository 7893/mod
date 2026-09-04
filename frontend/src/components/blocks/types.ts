import type { Component } from 'vue'

/** 语义色调。各屏一律用这套枚举，不再各自写 .accent / .highlight / .pass 等局部类。 */
export type BlockTone = 'default' | 'accent' | 'success' | 'warning' | 'danger'

/**
 * 指标卡的数据形态。
 *
 * 重构前，同一个「一组数字 + 标签」的概念在七处各写了一遍
 * （stage-card / t-stat / c-stat-box / q-card / stg-kpis / ops-item / detail-metrics），
 * 结果是七套间距、七套列数策略、七套 bug。统一到这里之后，
 * 各屏只负责把数据整理成 MetricItem[]，排版和高度规则由 MetricGrid 保证。
 */
export interface MetricItem {
  label: string
  value: string | number
  /** 数值后缀，如「家」「%」「笔」。用小字号弱化，不与数值抢视线。 */
  unit?: string
  /** 卡片底部的一行补充说明。 */
  hint?: string
  icon?: Component
  tone?: BlockTone
  /** 给了就在数值下渲染一条进度条，取值 0–100。 */
  progress?: number
  /** 底部小计，如「总 5992 / 完 3689 / 行 296」。 */
  meta?: { label: string; value: string | number }[]
}

/** 列表行：名称 + 可选进度条 + 右侧数值。 */export interface StatRow {
  id?: string | number
  label: string
  /** 名称下方的次要说明，如批次状态、责任组。 */
  sub?: string
  value?: string | number
  unit?: string
  tone?: BlockTone
  /** 条形占比 0–100。给了才渲染进度条。 */
  progress?: number
  /** 第二条进度条，用于「建设 / 上线」这类双指标对照。 */
  progressAlt?: number
  progressLabel?: string
  progressAltLabel?: string
  /** 序号，给了则在行首显示排名徽标。 */
  rank?: number
  icon?: Component
}

/**
 * 状态条目：图标或色点 + 标题 + 说明，可选跳转。
 *
 * 取代原先散在四处的 risk-item / gov-item / F6 预警 / aux-link，
 * 它们结构完全一致，只是各自写了一套间距和颜色。
 */
export interface StatusRow {
  id?: string | number
  title: string
  desc?: string
  icon?: Component
  tone?: BlockTone
  /** 用色点代替图标，色点取 tone 的语义色。 */
  dot?: boolean
  /** 给了则整行渲染为链接。 */
  href?: string
}
