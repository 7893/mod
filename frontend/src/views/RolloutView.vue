<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, GaugeChart, HeatmapChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent, VisualMapComponent } from 'echarts/components'
import CockpitPanel from '../components/CockpitPanel.vue'
import PanelLegend from '../components/PanelLegend.vue'
import RolloutLedgerTable from '../components/RolloutLedgerTable.vue'
import { calmAnimation, chartInk, chartPalette, chartTooltip } from '../charts/theme.ts'
import { buildCoverageComposition, buildRolloutComposition } from '../charts/panelData.ts'
import { createCoverageOption, createRolloutCompositionOption } from '../charts/panelOptions.ts'
import { createRolloutCommandOption, createRolloutTrendMatrixOption } from '../charts/rolloutOptions.ts'
import { useProjectStore } from '../stores/project.ts'

use([CanvasRenderer, BarChart, GaugeChart, HeatmapChart, PieChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent, VisualMapComponent])

const store = useProjectStore()

const format = (value: number | undefined) => (
  value === undefined ? '—' : new Intl.NumberFormat('zh-CN').format(value)
)

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
    .sort((a, b) => b.launched - a.launched || b.total - a.total)
})

const topProvinces = computed(() => provinceRolloutRanking.value.slice(0, 6))

const coveredProvinceCount = computed(() => new Set(store.provinceSummary.map((p) => p.name)).size)

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
      <div class="grid grid-cols-12 gap-3 h-24 min-h-0">
        <section class="col-span-9 pr-3 border-r border-surface-veil-06 min-h-0">
          <VChart class="w-full h-full min-h-0" :option="rolloutCommandOption" autoresize />
        </section>
        <section class="col-span-3 grid grid-cols-2 grid-rows-2 min-h-0">
          <div class="pr-2 pb-1 border-r border-b border-surface-veil-06 flex flex-col justify-center min-h-0"><span class="text-cockpit-xs text-slate-500">纳管单位</span><b class="font-mono text-cockpit-md text-slate-100 mt-0.5">{{ format(store.snapshot.overview.orgTotal) }}</b></div>
          <div class="pl-2 pb-1 border-b border-surface-veil-06 flex flex-col justify-center min-h-0"><span class="text-cockpit-xs text-slate-500">推广批次</span><b class="font-mono text-cockpit-md text-sky-400 mt-0.5">{{ batches.length }} 批</b></div>
          <div class="pr-2 pt-1 border-r border-surface-veil-06 flex flex-col justify-center min-h-0"><span class="text-cockpit-xs text-slate-500">覆盖省份</span><b class="font-mono text-cockpit-md text-slate-100 mt-0.5">{{ coveredProvinceCount }} 省</b></div>
          <div class="pl-2 pt-1 flex flex-col justify-center min-h-0"><span class="text-cockpit-xs text-slate-500">联系人</span><b class="font-mono text-cockpit-md text-emerald-400 mt-0.5">{{ format(store.snapshot.overview.contactsTotal) }}</b></div>
        </section>
      </div>
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
          <div v-else class="flex h-full items-center justify-center text-cockpit-xs text-slate-500">暂无批次历史快照</div>
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
            <div class="col-span-3 grid grid-rows-3 h-full text-cockpit-xs min-h-0">
              <div class="flex items-center justify-between border-b border-surface-veil-06 gap-2 min-w-0">
                <span class="text-slate-400 truncate">联系人总数</span>
                <b class="font-mono text-cockpit-sm text-sky-400 flex-shrink-0">{{ format(store.snapshot.overview.contactsTotal) }}</b>
              </div>
              <div class="flex items-center justify-between border-b border-surface-veil-06 gap-2 min-w-0">
                <span class="text-slate-400 truncate">已覆盖单位</span>
                <b class="font-mono text-cockpit-sm text-emerald-400 flex-shrink-0">{{ format(contactCoverage?.covered) }}</b>
              </div>
              <div class="flex items-center justify-between gap-2 min-w-0">
                <span class="text-slate-400 truncate">待补齐缺口</span>
                <b class="font-mono text-cockpit-sm text-amber-400 flex-shrink-0">{{ format(contactCoverage?.gap) }}</b>
              </div>
            </div>
          </div>
        </CockpitPanel>
      </div>

      <!-- C6: 单位台账表格与分页组件 -->
      <RolloutLedgerTable class="min-h-0" />
    </div>
  </div>
</template>
