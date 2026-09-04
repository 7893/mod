<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { AlertTriangle, CheckCircle2, Clock, ShieldAlert } from 'lucide-vue-next'
import CockpitPanel from '../components/CockpitPanel.vue'
import {
  calmAnimation,
  categoryAxis,
  chartInk,
  chartPalette,
  chartSeriesColors,
  chartTooltip,
  compactGrid,
  valueAxis,
} from '../charts/theme.ts'
import MetricGrid from '../components/blocks/MetricGrid.vue'
import ChartBlock from '../components/blocks/ChartBlock.vue'
import type { MetricItem } from '../components/blocks/types.ts'
import { useProjectStore } from '../stores/project.ts'

use([CanvasRenderer, BarChart, PieChart, GridComponent, TooltipComponent, LegendComponent])

const store = useProjectStore()

/** E5 每个阶段卡内的五项指标，交给 MetricGrid 统一排版。 */
function stageKpis(stg: {
  unresolved: number
  resolved: number
  bug: number
  data: number
  integ: number
}): MetricItem[] {
  return [
    { label: '未解决', value: stg.unresolved, tone: 'warning' },
    { label: '已解决', value: stg.resolved, tone: 'success' },
    { label: 'Bug', value: stg.bug },
    { label: '数据', value: stg.data },
    { label: '接口', value: stg.integ },
  ]
}

const summary = computed(() => store.snapshot.issuesSummary || {
  latestDate: '2026-09-03',
  totalUnresolved: 3521,
  totalResolved: 3515,
  totalIssues: 7036,
  closeRate: 49.96,
  highRisk: 1001,
  mediumRisk: 2510,
  lowRisk: 5001,
  byStage: [],
  byBatch: [],
})

const e1SummaryItems = computed<MetricItem[]>(() => [
  {
    label: '高风险',
    value: summary.value.highRisk !== undefined ? summary.value.highRisk.toLocaleString() : '—',
    unit: '项',
    tone: 'danger',
    icon: ShieldAlert,
  },
  {
    label: '未解决',
    value: summary.value.totalUnresolved !== undefined ? summary.value.totalUnresolved.toLocaleString() : '—',
    unit: '项',
    tone: 'warning',
    icon: AlertTriangle,
  },
  {
    label: '已解决',
    value: summary.value.totalResolved !== undefined ? summary.value.totalResolved.toLocaleString() : '—',
    unit: '项',
    tone: 'success',
    icon: CheckCircle2,
  },
  {
    label: '闭环率',
    value: summary.value.closeRate !== undefined ? `${summary.value.closeRate}` : '—',
    unit: '%',
    icon: Clock,
  },
])

const typeBreakdown = computed(() => {
  const res = { bug: 0, req: 0, conf: 0, data: 0, integ: 0, op: 0 }
  summary.value.byStage?.forEach((stg) => {
    res.bug += stg.bug || 0
    res.req += stg.req || 0
    res.conf += stg.conf || 0
    res.data += stg.data || 0
    res.integ += stg.integ || 0
    res.op += stg.op || 0
  })
  const hasCurrentBreakdown = Boolean(summary.value.byStage?.length)
  return [
    { label: 'Bug 缺陷', key: 'bug', count: hasCurrentBreakdown ? res.bug : 1493, color: chartSeriesColors[4] },
    { label: '数据问题', key: 'data', count: hasCurrentBreakdown ? res.data : 1543, color: chartSeriesColors[3] },
    { label: '运维操作', key: 'op', count: hasCurrentBreakdown ? res.op : 1032, color: chartSeriesColors[0] },
    { label: '配置错误', key: 'conf', count: hasCurrentBreakdown ? res.conf : 1019, color: chartSeriesColors[2] },
    { label: '接口集成', key: 'integ', count: hasCurrentBreakdown ? res.integ : 955, color: chartSeriesColors[1] },
    { label: '需求变更', key: 'req', count: hasCurrentBreakdown ? res.req : 994, color: chartSeriesColors[5] },
  ]
})

const typeStats = computed<MetricItem[]>(() =>
  typeBreakdown.value.map((t) => ({ label: t.label, value: t.count })),
)

const typeBarOption = computed(() => ({
  ...calmAnimation,
  tooltip: { trigger: 'axis', ...chartTooltip },
  grid: { ...compactGrid, bottom: 16 },
  xAxis: {
    ...categoryAxis,
    data: typeBreakdown.value.map((t) => t.label),
  },
  yAxis: valueAxis,
  series: [{
    name: '问题数量',
    type: 'bar',
    data: typeBreakdown.value.map((t) => ({ value: t.count, itemStyle: { color: t.color } })),
    barWidth: '46%', barMaxWidth: 56,
    itemStyle: { borderRadius: [3, 3, 0, 0] },
  }],
}))

const riskPieOption = computed(() => ({
  ...calmAnimation,
  tooltip: { trigger: 'item', ...chartTooltip },
  legend: {
    orient: 'vertical',
    right: 10,
    top: 'center',
    textStyle: { color: chartInk.textMuted, fontSize: 11 },
    itemWidth: 10,
    itemHeight: 10,
  },
  series: [{
    name: '风险等级',
    type: 'pie',
    radius: ['45%', '70%'],
    center: ['35%', '50%'],
    data: [
      { value: summary.value.highRisk, name: `高风险 (${summary.value.highRisk})`, itemStyle: { color: chartPalette.danger } },
      { value: summary.value.mediumRisk, name: `中风险 (${summary.value.mediumRisk})`, itemStyle: { color: chartPalette.warning } },
      { value: summary.value.lowRisk, name: `低风险 (${summary.value.lowRisk})`, itemStyle: { color: chartPalette.success } },
    ],
    label: { show: false },
  }],
}))
</script>

<template>
  <div class="flex flex-col gap-2.5 h-full min-h-0 w-full" data-zone="E">
    <!-- E1: 概览卡片 -->
    <CockpitPanel
      title="问题闭环与风险预警"
      zone="E1"
      :subtitle="`统计截至 ${summary.latestDate || store.snapshot.meta.asOfDate}，仅展示分类汇总`"
    >
      <MetricGrid :items="e1SummaryItems" variant="inline" :columns="4" />
    </CockpitPanel>

    <!-- 中部：E2 问题类型分布 + E3 风险等级构成 -->
    <div class="grid grid-cols-issues-top gap-2.5 min-h-[300px] max-h-[350px] flex-shrink-0">
      <CockpitPanel title="问题类型分布" zone="E2" subtitle="缺陷/数据/运维/配置/接口/需求 6 大维度">
        <ChartBlock :stats="typeStats" stats-position="bottom">
          <VChart :option="typeBarOption" autoresize />
        </ChartBlock>
      </CockpitPanel>

      <CockpitPanel title="风险等级构成" zone="E3" subtitle="高/中/低三级风险分布比例">
        <ChartBlock footnote="* 风险等级与问题汇总采用同一统计日口径">
          <VChart :option="riskPieOption" autoresize />
        </ChartBlock>
      </CockpitPanel>
    </div>

    <!-- 下部：E4 各批次问题汇总 -->
    <CockpitPanel title="各批次问题汇总" zone="E4" subtitle="8 批次未解决量与高中低风险分布" class="flex-shrink-0">
      <div class="grid grid-cols-4 gap-2.5 min-h-0">
        <div
          v-for="b in summary.byBatch"
          :key="b.batchId"
          class="flex flex-col justify-between p-2.5 rounded-xl bg-surface-veil-03 border border-surface-veil-06 min-h-0"
        >
          <div class="flex items-center justify-between gap-1 mb-2">
            <b class="text-cockpit-md font-semibold text-slate-100 truncate">{{ b.name }}</b>
            <span class="font-mono text-cockpit-xs text-amber-400 font-medium">
              未解决 {{ b.unresolved }}
            </span>
          </div>
          <div class="flex items-center justify-between gap-1.5">
            <div class="flex items-center gap-1 text-cockpit-xs font-medium px-2 py-0.5 rounded bg-rose-950/30 text-rose-400 border border-rose-500/20">
              <span>高</span>
              <b class="font-mono">{{ b.high }}</b>
            </div>
            <div class="flex items-center gap-1 text-cockpit-xs font-medium px-2 py-0.5 rounded bg-amber-950/30 text-amber-400 border border-amber-500/20">
              <span>中</span>
              <b class="font-mono">{{ b.medium }}</b>
            </div>
            <div class="flex items-center gap-1 text-cockpit-xs font-medium px-2 py-0.5 rounded bg-emerald-950/30 text-emerald-400 border border-emerald-500/20">
              <span>低</span>
              <b class="font-mono">{{ b.low }}</b>
            </div>
          </div>
        </div>
      </div>
    </CockpitPanel>

    <!-- 底部：E5 推进阶段状态 -->
    <CockpitPanel title="推进阶段状态" zone="E5" subtitle="各阶段闭环推进质量与分类结构" class="flex-1 min-h-0">
      <div class="grid gap-2.5 h-full min-h-0" :class="summary.byStage.length > 1 ? 'grid-cols-2' : 'grid-cols-1'">
        <div
          v-for="stg in summary.byStage"
          :key="stg.stage"
          class="flex flex-col justify-between p-3 rounded-xl bg-surface-veil-03 border border-surface-veil-06 min-h-0"
        >
          <div class="flex items-center justify-between pb-2 border-b border-surface-veil-06 mb-2">
            <b class="text-cockpit-md font-semibold text-slate-100 truncate">{{ stg.stage }}</b>
            <span class="font-mono text-cockpit-xs text-slate-400">共 {{ stg.total }} 项</span>
          </div>
          <MetricGrid :items="stageKpis(stg)" :columns="5" size="sm" fill />
        </div>
      </div>
    </CockpitPanel>
  </div>
</template>
