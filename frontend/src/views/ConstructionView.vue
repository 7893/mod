<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { formatCount as format } from '../formatters/metrics.ts'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, HeatmapChart, PieChart, RadarChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  RadarComponent,
  VisualMapComponent,
} from 'echarts/components'
import {
  Database,
} from 'lucide-vue-next'
import CockpitPanel from '../components/CockpitPanel.vue'
import PanelLegend from '../components/PanelLegend.vue'
import ConstructionLedger from '../components/ConstructionLedger.vue'
import OverviewBand from '../components/blocks/OverviewBand.vue'
import StatList from '../components/blocks/StatList.vue'
import type { StatRow } from '../components/blocks/types.ts'
import {
  calmAnimation,
  chartInk,
  chartPalette,
  chartTooltip,
} from '../charts/theme.ts'
import { buildOverviewComposition, buildTaskStageSeries } from '../charts/panelData.ts'
import {
  createTaskStageMatrixOption,
  createTaskStageRadarOption,
  createTrainingFunnelOption,
  createLaunchGateOption,
} from '../charts/constructionOptions.ts'
import { useProjectStore } from '../stores/project.ts'

use([
  CanvasRenderer,
  BarChart,
  HeatmapChart,
  PieChart,
  RadarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  RadarComponent,
  VisualMapComponent,
])

const route = useRoute()
const router = useRouter()
const store = useProjectStore()

const activeTab = ref<'overview' | 'ledger'>(route.query.tab === 'ledger' ? 'ledger' : 'overview')
const ledgerStatusFilter = ref('全部')
const ledgerReadinessFilter = ref('全部')

watch(() => route.query.tab, (val) => {
  if (val === 'ledger') activeTab.value = 'ledger'
  else if (val === 'overview' || !val) activeTab.value = 'overview'
})

function switchTab(tab: 'overview' | 'ledger') {
  activeTab.value = tab
  void router.replace({ query: { ...route.query, tab } })
}

function openLedgerWithFilter(statusFilter = '全部') {
  ledgerStatusFilter.value = statusFilter
  ledgerReadinessFilter.value = '全部'
  switchTab('ledger')
}

function handleReadinessClick(params: { name?: string }) {
  if (!params.name || !['已导入', '已校验', '收集中', '未收集'].includes(params.name)) return
  ledgerStatusFilter.value = '全部'
  ledgerReadinessFilter.value = params.name
  switchTab('ledger')
}

const taskStages = computed(() => store.snapshot.construction?.taskStages || [])

const constructionSummary = computed(() => store.snapshot.construction)
const trainingSummary = computed(() => constructionSummary.value?.trainingSummary)
const readinessSummary = computed(() => constructionSummary.value?.dataReadinessSummary)

const constructionComposition = computed(() => buildOverviewComposition(
  constructionSummary.value?.totalTasks,
  [
    { label: '已完成', value: constructionSummary.value?.completedTasks, tone: 'success' },
    { label: '进行中', value: constructionSummary.value?.inProgressTasks, tone: 'accent' },
    { label: '未开始', value: constructionSummary.value?.notStartedTasks, tone: 'neutral' },
  ],
))

const b1Primary = computed(() => ({
  label: '综合完成率',
  value: constructionSummary.value?.avgProgress ?? '—',
  unit: constructionSummary.value ? '%' : undefined,
  tone: 'accent' as const,
  hint: '全量建设任务平均进度',
}))

const b1Facts = computed(() => [
  { label: '任务总数', value: format(constructionSummary.value?.totalTasks), unit: '项' },
  { label: '纳管单位', value: format(store.snapshot.overview.orgTotal), unit: '家' },
  { label: '培训场次', value: format(trainingSummary.value?.totalSessions), unit: '场' },
])

const RANK_LIMIT = 8

const provinceRanking = computed(() =>
  [...store.provinceSummary].sort((a, b) => b.value - a.value).slice(0, RANK_LIMIT),
)

/**
 * 排行条的条长映射：拉伸到 [34%, 100%]
 */
const rankBarWidth = (value: number) => {
  const values = provinceRanking.value.map((p) => p.value)
  if (!values.length) return 100
  const max = Math.max(...values)
  const min = Math.min(...values)
  if (max - min < 0.01) return 100
  return 34 + ((value - min) / (max - min)) * 66
}

const rankRows = computed<StatRow[]>(() =>
  provinceRanking.value.map((p) => ({
    id: p.name,
    label: p.name,
    value: p.value,
    unit: '%',
    progress: rankBarWidth(p.value),
  })),
)

// 色值统一取自 charts/theme.ts
const chartColors = {
  accent: chartPalette.accent,
  success: chartPalette.success,
  warning: chartPalette.warning,
  muted: chartPalette.neutral,
  textMuted: chartInk.textMuted,
}

const stageMatrixOption = computed(() => createTaskStageMatrixOption(buildTaskStageSeries(taskStages.value)))
const stageRadarOption = computed(() => createTaskStageRadarOption(buildTaskStageSeries(taskStages.value)))
const launchGateStages = computed(() => buildTaskStageSeries(taskStages.value).filter((stage) => (
  ['期初数据', '接口联调', '双轨验证', '用户培训'].includes(stage.name)
)))
const launchGateOption = computed(() => createLaunchGateOption(launchGateStages.value))
const trainingFunnelOption = computed(() => createTrainingFunnelOption(trainingSummary.value))

const readinessPieOption = computed(() => ({
  ...calmAnimation,
  tooltip: {
    trigger: 'item',
    ...chartTooltip,
  },
  legend: {
    orient: 'vertical',
    right: 10,
    top: 'center',
    textStyle: { color: chartColors.textMuted, fontSize: 11 },
    itemWidth: 10,
    itemHeight: 10,
  },
  series: [{
    name: '数据准备度',
    type: 'pie',
    radius: ['45%', '70%'],
    center: ['35%', '50%'],
    data: [
      { value: readinessSummary.value?.imported ?? 0, name: '已导入', itemStyle: { color: chartColors.accent } },
      { value: readinessSummary.value?.verified ?? 0, name: '已校验', itemStyle: { color: chartColors.success } },
      { value: readinessSummary.value?.collecting ?? 0, name: '收集中', itemStyle: { color: chartColors.warning } },
      { value: readinessSummary.value?.notCollected ?? 0, name: '未收集', itemStyle: { color: chartColors.muted } },
    ],
    label: { show: false },
  }],
}))
</script>

<template>
  <div class="w-full h-full p-3 bg-surface-base flex flex-col gap-2.5 overflow-hidden" data-zone="B">
    <!-- B1: 进度总览 (去除顶部 tab 切换，专注建设全景，B-1) -->
    <CockpitPanel
      title="系统建设进度全景"
      zone="B1"
      :subtitle="`${format(store.snapshot.overview.orgTotal)} 家单位 · ${format(constructionSummary?.totalTasks)} 项任务 · ${format(trainingSummary?.totalSessions)} 场培训`"
      class="flex-shrink-0"
    >
      <OverviewBand
        :primary="b1Primary"
        chart-label="任务状态构成"
        :total="constructionComposition.total"
        :parts="constructionComposition.parts"
        :facts="b1Facts"
      />
    </CockpitPanel>

    <!-- 建设全景主区 -->
    <main v-if="activeTab === 'overview'" class="flex-1 min-h-0 grid grid-cols-construction grid-rows-construction gap-2.5">
      <!-- B2: 状态矩阵承载 24 个任务数据点，雷达图补充八阶段均衡性判断 -->
      <CockpitPanel title="建设阶段作战矩阵" zone="B2" subtitle="任务状态密度与八阶段完成度轮廓" class="col-span-8 min-h-0">
        <div class="grid grid-cols-12 gap-2 h-full min-h-0">
          <section class="col-span-9 flex flex-col min-h-0 pr-3 border-r border-surface-veil-06">
            <div class="flex items-center justify-between pb-1 text-cockpit-xs">
              <span class="font-medium text-slate-300">阶段 × 状态任务矩阵</span>
              <span class="font-mono text-slate-500">8 阶段 · 24 数据格</span>
            </div>
            <VChart class="w-full flex-1 min-h-0" :option="stageMatrixOption" autoresize />
          </section>
          <section class="col-span-3 flex flex-col min-h-0">
            <div class="flex items-center justify-between pb-1 text-cockpit-xs">
              <span class="font-medium text-slate-300">阶段均衡轮廓</span>
              <span class="font-mono text-sky-400">{{ constructionSummary?.avgProgress ?? '—' }}%</span>
            </div>
            <VChart class="w-full flex-1 min-h-0" :option="stageRadarOption" autoresize />
          </section>
        </div>
      </CockpitPanel>

      <!-- B3: 省域建设排行 -->
      <CockpitPanel title="省域建设领先榜" zone="B3" subtitle="完成率前八" class="col-span-4">
        <StatList :rows="rankRows" ranked density="dense" scroll />
      </CockpitPanel>

      <!-- B4: 关键上线门禁为主，培训只保留总体转化漏斗 -->
      <CockpitPanel title="上线门禁攻坚" zone="B4" subtitle="关键任务推进与参培认证转化" class="col-span-8 min-h-0">
        <template #actions>
          <PanelLegend :items="[
            { label: '已完成', tone: 'success' },
            { label: '进行中', tone: 'accent' },
            { label: '待启动', tone: 'neutral' },
          ]" />
        </template>
        <div class="grid grid-cols-12 gap-2 h-full min-h-0">
          <section class="col-span-8 flex flex-col min-h-0 pr-3 border-r border-surface-veil-06">
            <div class="flex items-center justify-between pb-1 text-cockpit-xs">
              <span class="font-medium text-slate-300">四道关键上线门禁</span>
              <span class="font-mono text-slate-500">完成 / 推进 / 待启动</span>
            </div>
            <VChart v-if="launchGateStages.length" class="w-full flex-1 min-h-0" :option="launchGateOption" autoresize />
            <div v-else class="flex flex-1 items-center justify-center text-cockpit-xs text-slate-500">暂无关键门禁任务数据</div>
          </section>
          <section class="col-span-4 flex flex-col min-h-0">
            <div class="flex items-center justify-between pb-1 text-cockpit-xs">
              <span class="font-medium text-slate-300">参培认证漏斗</span>
              <span class="font-mono text-emerald-400">通过 {{ format(trainingSummary?.totalPassed) }} 人</span>
            </div>
            <VChart v-if="trainingSummary" class="w-full flex-1 min-h-0" :option="trainingFunnelOption" autoresize />
            <div v-else class="flex flex-1 items-center justify-center text-cockpit-xs text-slate-500">暂无培训转化数据</div>
          </section>
        </div>
      </CockpitPanel>

      <!-- B5: 图表本身承担状态下钻，避免图例与按钮重复 -->
      <CockpitPanel title="期初数据准备度" zone="B5" subtitle="单位数据状态" class="col-span-4">
        <template #actions>
          <button
            type="button"
            class="flex items-center gap-1.5 px-2.5 py-1 rounded bg-sky-500/15 text-sky-400 border border-sky-500/30 hover:bg-sky-500/25 transition-colors text-cockpit-xs font-medium cursor-pointer"
            @click="openLedgerWithFilter('全部')"
          >
            <Database :size="12" />
            <span>台账下钻</span>
          </button>
        </template>
        <div class="flex h-full min-h-0 flex-col gap-2">
          <VChart class="min-h-0 flex-1 cursor-pointer" :option="readinessPieOption" autoresize @click="handleReadinessClick" />
          <p class="text-center text-cockpit-xs text-slate-500 flex-shrink-0">点击扇区，按数据准备状态进入单位台账</p>
        </div>
      </CockpitPanel>
    </main>

    <!-- 并入的数据准备台账下钻主区 -->
    <main v-else class="flex-1 min-h-0 flex flex-col">
      <ConstructionLedger
        :initial-filter="ledgerStatusFilter"
        :initial-readiness-filter="ledgerReadinessFilter"
        @back="switchTab('overview')"
      />
    </main>
  </div>
</template>
