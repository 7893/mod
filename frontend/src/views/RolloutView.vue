<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent } from 'echarts/components'
import CockpitPanel from '../components/CockpitPanel.vue'
import ChartBlock from '../components/blocks/ChartBlock.vue'
import OverviewBand from '../components/blocks/OverviewBand.vue'
import RolloutLedgerTable from '../components/RolloutLedgerTable.vue'
import type { MetricItem } from '../components/blocks/types.ts'
import { calmAnimation, chartInk, chartPalette } from '../charts/theme.ts'
import { buildCoverageComposition, buildOverviewComposition, buildRolloutComposition } from '../charts/panelData.ts'
import { createCoverageOption, createRolloutCompositionOption } from '../charts/panelOptions.ts'
import { useProjectStore } from '../stores/project.ts'

use([CanvasRenderer, BarChart, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent])

const store = useProjectStore()

const format = (value: number | undefined) => (
  value === undefined ? '—' : new Intl.NumberFormat('zh-CN').format(value)
)

const batches = computed(() => store.snapshot.rollout || [])

const rolloutOverviewComposition = computed(() => {
  const overview = store.snapshot.overview
  const pending = Math.max(0, (overview.orgTotal ?? 0) - (overview.launched ?? 0) - (overview.dual ?? 0))
  return buildOverviewComposition(overview.orgTotal, [
    { label: '已上线', value: overview.launched, tone: 'success' },
    { label: '双轨运行', value: overview.dual, tone: 'warning' },
    { label: '待推进', value: pending, tone: 'neutral' },
  ])
})

const c1Primary = computed(() => ({
  label: '总体上线率',
  value: store.snapshot.overview.launchedPct ?? '—',
  unit: '%',
  tone: 'success' as const,
  hint: '正式上线单位占总纳管比例',
}))

const c1Facts = computed(() => [
  { label: '纳管单位', value: format(store.snapshot.overview.orgTotal), unit: '家' },
  { label: '推广批次', value: batches.value.length, unit: '批' },
  { label: '覆盖省份', value: 34, unit: '省' },
])

// 色值统一取自 charts/theme.ts，避免图表区与页面外壳出现两套蓝绿黄
const chartColors = {
  accent: chartPalette.accent,
  warning: chartPalette.warning,
  success: chartPalette.success,
  bg: chartInk.bgTooltip,
  border: chartInk.border,
  textMuted: chartInk.textMuted,
}

const rolloutComposition = computed(() => buildRolloutComposition(batches.value))

const batchCompositionOption = computed(() => createRolloutCompositionOption(rolloutComposition.value))

const contactCoverage = computed(() => buildCoverageComposition(
  store.snapshot.overview.orgTotal,
  store.snapshot.overview.contactsCoveredOrgs,
))

const contactCoverageOption = computed(() => createCoverageOption(contactCoverage.value))

const batchChartOption = computed(() => ({
  ...calmAnimation,
  tooltip: {
    trigger: 'axis',
    backgroundColor: chartColors.bg,
    borderColor: chartColors.border,
    textStyle: { color: chartInk.textPrimary, fontSize: 12 },
  },
  grid: { left: 12, right: 12, top: 24, bottom: 24, containLabel: true },
  xAxis: {
    type: 'category',
    data: batches.value.map((v) => v.name),
    axisLine: { lineStyle: { color: chartColors.border } },
    axisLabel: { color: chartColors.textMuted, fontSize: 11 },
  },
  yAxis: {
    type: 'value',
    max: 100,
    splitLine: { lineStyle: { color: chartColors.border, opacity: 0.4 } },
    axisLabel: { color: chartColors.textMuted, fontSize: 11, formatter: '{value}%' },
  },
  series: [
    {
      name: '上线率',
      type: 'bar',
      data: batches.value.map((v) => v.launchedPct),
      barWidth: '34%', barMaxWidth: 34,
      itemStyle: { color: chartColors.accent, borderRadius: [3, 3, 0, 0] },
    },
    {
      name: '建设完成度',
      type: 'line',
      data: batches.value.map((v) => v.constructionPct),
      symbolSize: 5,
      lineStyle: { color: chartColors.warning, width: 2 },
      itemStyle: { color: chartColors.warning },
    },
  ],
}))

const provinceRolloutRanking = computed(() => {
  const list = [...store.provinceSummary]
  return list
    .map((p) => ({
      ...p,
      launchedPct: p.total > 0 ? Math.round((p.launched * 100) / p.total) : 0,
      unlaunched: Math.max(0, p.total - p.launched - p.dual),
    }))
    .sort((a, b) => b.launched - a.launched || b.total - a.total)
})

const topProvinces = computed(() => provinceRolloutRanking.value.slice(0, 6))

const c4Stats = computed<MetricItem[]>(() => [
  { label: '覆盖省份', value: 34 },
  { label: '最高上线', value: topProvinces.value[0]?.name || '—' },
  { label: '平均上线率', value: String(store.snapshot.overview.launchedPct || 37.4), unit: '%' },
])

const provinceRolloutOption = computed(() => ({
  ...calmAnimation,
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    backgroundColor: chartColors.bg,
    borderColor: chartColors.border,
    textStyle: { color: chartInk.textPrimary, fontSize: 12 },
  },
  legend: {
    data: ['已上线', '双轨', '其他'],
    top: 0,
    right: 4,
    textStyle: { color: chartColors.textMuted, fontSize: 10 },
    itemWidth: 10,
    itemHeight: 8,
  },
  grid: { left: 4, right: 10, top: 26, bottom: 4, containLabel: true },
  xAxis: {
    type: 'value',
    splitLine: { lineStyle: { color: chartColors.border, opacity: 0.4 } },
    axisLabel: { color: chartColors.textMuted, fontSize: 10 },
  },
  yAxis: {
    type: 'category',
    data: topProvinces.value.map((v) => v.name).reverse(),
    axisLine: { lineStyle: { color: chartColors.border } },
    // interval: 0 强制每个省份都出标签。默认策略在容器变矮时会隔项跳过，
    // 结果画了 6 条却只标出 3 个省名，读者无法把条形对应到省份。
    axisLabel: { color: chartColors.textMuted, fontSize: 11, interval: 0 },
  },
  series: [
    {
      name: '已上线',
      type: 'bar',
      stack: 'total',
      barMaxWidth: 14,
      data: topProvinces.value.map((v) => v.launched).reverse(),
      itemStyle: { color: chartColors.accent },
    },
    {
      name: '双轨',
      type: 'bar',
      stack: 'total',
      data: topProvinces.value.map((v) => v.dual).reverse(),
      itemStyle: { color: chartColors.warning },
    },
    {
      name: '其他',
      type: 'bar',
      stack: 'total',
      data: topProvinces.value.map((v) => v.unlaunched).reverse(),
      itemStyle: { color: chartColors.border },
    },
  ],
}))
</script>

<template>
  <div class="w-full h-full p-3 bg-surface-base flex flex-col gap-2.5 overflow-hidden" data-zone="C">
    <!-- C1: 概览指标 -->
    <CockpitPanel
      title="推广上线与批次台账"
      zone="C1"
      :subtitle="`${batches.length} 个批次 · ${format(store.snapshot.overview.orgTotal)} 家单位 · 已上线 ${format(store.snapshot.overview.launched)} 家 (${store.snapshot.overview.launchedPct || 37.4}%)`"
      class="flex-shrink-0"
    >
      <OverviewBand
        :primary="c1Primary"
        chart-label="推广状态构成"
        :total="rolloutOverviewComposition.total"
        :parts="rolloutOverviewComposition.parts"
        :facts="c1Facts"
      />
    </CockpitPanel>

    <!-- C2: 用批次堆叠图替代 8 张拥挤工序卡 -->
    <CockpitPanel
      title="批次推进工序梯队"
      zone="C2"
      subtitle="8 批次单位构成 · 已上线 / 双轨 / 待推进"
      class="flex-shrink-0"
    >
      <VChart class="w-full h-28 min-h-0" :option="batchCompositionOption" autoresize />
    </CockpitPanel>

    <!-- 中部三栏：C3 上线趋势 + C4 省域上线分布 + C5 项目联系人 (弹性优先，Guardrail 扩大为 min-h-[200px] max-h-[320px]，C-2) -->
    <div class="grid grid-cols-rollout-mid gap-2.5 min-h-[200px] max-h-[320px] flex-1">
      <CockpitPanel title="上线趋势" zone="C3" subtitle="批次演进与完成度">
        <VChart class="w-full h-full min-h-0" :option="batchChartOption" autoresize />
      </CockpitPanel>

      <CockpitPanel title="省域上线分布" zone="C4" subtitle="34 省上线率排行">
        <ChartBlock :stats="c4Stats">
          <VChart class="w-full h-full min-h-0" :option="provinceRolloutOption" autoresize />
        </ChartBlock>
      </CockpitPanel>

      <CockpitPanel title="项目联系人" zone="C5" subtitle="组织覆盖与专员">
        <div class="grid grid-cols-2 h-full min-h-0 items-center gap-2">
          <VChart class="w-full h-full min-h-0" :option="contactCoverageOption" autoresize />
          <div class="flex flex-col justify-center gap-2 text-cockpit-sm">
            <div class="flex items-center justify-between border-b border-surface-veil-06 pb-1.5">
              <span class="text-slate-400">联系人总数</span>
              <b class="font-mono text-sky-400">{{ format(store.snapshot.overview.contactsTotal) }}</b>
            </div>
            <div class="flex items-center justify-between border-b border-surface-veil-06 pb-1.5">
              <span class="text-slate-400">已覆盖单位</span>
              <b class="font-mono text-emerald-400">{{ format(contactCoverage?.covered) }}</b>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-slate-400">待补齐缺口</span>
              <b class="font-mono text-amber-400">{{ format(contactCoverage?.gap) }}</b>
            </div>
          </div>
        </div>
      </CockpitPanel>
    </div>

    <!-- C6: 单位台账表格与分页组件 -->
    <RolloutLedgerTable class="flex-1 min-h-0" />
  </div>
</template>
