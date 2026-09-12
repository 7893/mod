<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, GaugeChart, HeatmapChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent, VisualMapComponent } from 'echarts/components'
import CockpitPanel from '../components/CockpitPanel.vue'
import PanelLegend from '../components/PanelLegend.vue'
import CommandBand from '../components/blocks/CommandBand.vue'
import EmptyNote from '../components/blocks/EmptyNote.vue'
import StatList from '../components/blocks/StatList.vue'
import type { MetricItem, StatRow } from '../components/blocks/types.ts'
import RolloutLedgerTable from '../components/RolloutLedgerTable.vue'
import { calmAnimation, chartInk, chartPalette, chartTooltip } from '../charts/theme.ts'
import { buildCoverageComposition, buildRolloutComposition } from '../charts/panelData.ts'
import { createCoverageOption, createRolloutCompositionOption } from '../charts/panelOptions.ts'
import { createRolloutCommandOption, createRolloutTrendMatrixOption } from '../charts/rolloutOptions.ts'
import { formatCount as format } from '../formatters/metrics.ts'
import { useProjectStore } from '../stores/project.ts'

use([CanvasRenderer, BarChart, GaugeChart, HeatmapChart, PieChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent, VisualMapComponent])

const store = useProjectStore()

const batches = computed(() => store.snapshot.rollout || [])

const rolloutCommandOption = computed(() => createRolloutCommandOption({
  total: store.snapshot.overview.orgTotal ?? 0,
  launched: store.snapshot.overview.launched ?? 0,
  dual: store.snapshot.overview.dual ?? 0,
}))

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

const rolloutTrend = computed(() => store.snapshot.rolloutTrend ?? [])
const rolloutTrendOption = computed(() => createRolloutTrendMatrixOption(rolloutTrend.value))

const provinceRolloutRanking = computed(() => {
  const list = [...store.provinceSummary]
  return list
    .map((p) => ({
      ...p,
      launchedPct: p.total > 0 ? Math.round((p.launched * 100) / p.total) : 0,
      unlaunched: Math.max(0, p.total - p.launched - p.dual),
    }))
    .sort((a, b) => b.launchedPct - a.launchedPct || b.launched - a.launched || a.name.localeCompare(b.name, 'zh-CN'))
})

const topProvinces = computed(() => provinceRolloutRanking.value.slice(0, 6))

const coveredProvinceCount = computed(() => new Set(store.provinceSummary.map((p) => p.name)).size)

const commandFacts = computed<MetricItem[]>(() => [
  { label: '纳管单位', value: format(store.snapshot.overview.orgTotal) },
  { label: '推广批次', value: batches.value.length, unit: '批', tone: 'accent' },
  { label: '覆盖省份', value: coveredProvinceCount.value, unit: '省' },
  { label: '联系人', value: format(store.snapshot.overview.contactsTotal), tone: 'success' },
])

const contactFacts = computed<StatRow[]>(() => [
  { label: '联系人总数', value: format(store.snapshot.overview.contactsTotal), tone: 'accent' },
  { label: '已覆盖单位', value: format(contactCoverage.value?.covered), tone: 'success' },
  { label: '待补齐缺口', value: format(contactCoverage.value?.gap), tone: 'warning' },
])

const provinceRolloutOption = computed(() => ({
  ...calmAnimation,
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    ...chartTooltip,
  },
  grid: { left: 4, right: 10, top: 4, bottom: 4, containLabel: true },
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
    <!-- C1: 推广仪表与三段状态漏斗，替代通用 OverviewBand -->
    <CockpitPanel
      title="推广攻坚总盘"
      zone="C1"
      subtitle="总体上线水位、在途单位结构与推广覆盖上下文"
      class="flex-shrink-0"
    >
      <CommandBand :facts="commandFacts" :fact-columns="2" align="center">
        <template #chart>
          <VChart class="w-full h-full min-h-0" :option="rolloutCommandOption" autoresize />
        </template>
      </CommandBand>
    </CockpitPanel>

    <!-- C2: 横向比较各批次单位当前所处推广状态 -->
    <CockpitPanel
      title="各批次单位推进状态"
      zone="C2"
      subtitle="比较每批已上线、双轨运行与待推进单位构成"
      class="h-44 flex-shrink-0"
    >
      <template #actions>
        <PanelLegend :items="[
          { label: '已上线', tone: 'success' },
          { label: '双轨', tone: 'warning' },
          { label: '待推进', tone: 'neutral' },
        ]" />
      </template>
      <VChart class="w-full h-full min-h-0" :option="batchCompositionOption" autoresize />
    </CockpitPanel>

    <div class="grid grid-rows-rollout-body gap-2.5 flex-1 min-h-0">
      <!-- C3 为主分析画布；C4/C5 作为右侧上下辅助区，不再与 C3 等权占面 -->
      <div class="grid grid-cols-rollout-analysis grid-rows-rollout-analysis gap-2.5 min-h-0">
        <CockpitPanel title="批次上线爬坡矩阵" zone="C3" subtitle="历史快照中的批次上线率与双轨率" class="col-span-8 row-span-2">
          <VChart v-if="rolloutTrend.length" class="w-full h-full min-h-0" :option="rolloutTrendOption" autoresize />
          <EmptyNote v-else>暂无批次历史快照</EmptyNote>
        </CockpitPanel>

        <CockpitPanel title="省域上线分布" zone="C4" subtitle="上线率前六" class="col-span-4 min-h-0">
          <template #actions>
            <PanelLegend compact :items="[
              { label: '已上线', tone: 'accent' },
              { label: '双轨', tone: 'warning' },
              { label: '其他', tone: 'neutral' },
            ]" />
          </template>
          <VChart class="w-full h-full min-h-0" :option="provinceRolloutOption" autoresize />
        </CockpitPanel>

        <CockpitPanel title="项目联系人" zone="C5" subtitle="组织覆盖与专员" class="col-span-4 min-h-0">
          <div class="grid grid-cols-5 h-full min-h-0 gap-2 items-center">
            <VChart class="col-span-2 w-full h-full min-h-0" :option="contactCoverageOption" autoresize />
            <StatList class="col-span-3 self-stretch" :rows="contactFacts" flat density="dense" />
          </div>
        </CockpitPanel>
      </div>

      <!-- C6: 单位台账表格与分页组件 -->
      <RolloutLedgerTable />
    </div>
  </div>
</template>
