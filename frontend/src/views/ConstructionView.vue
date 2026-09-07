<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import {
  Database,
} from 'lucide-vue-next'
import CockpitPanel from '../components/CockpitPanel.vue'
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
  createTaskStageOverviewOption,
  createTrainingFunnelOption,
  createTrainingConversionOption,
  createTrainingMixOption,
} from '../charts/constructionOptions.ts'
import { useProjectStore } from '../stores/project.ts'

use([CanvasRenderer, BarChart, PieChart, GridComponent, TooltipComponent, LegendComponent])

const route = useRoute()
const router = useRouter()
const store = useProjectStore()

const activeTab = ref<'overview' | 'ledger'>(route.query.tab === 'ledger' ? 'ledger' : 'overview')
const ledgerFilter = ref('全部')

watch(() => route.query.tab, (val) => {
  if (val === 'ledger') activeTab.value = 'ledger'
  else if (val === 'overview' || !val) activeTab.value = 'overview'
})

function switchTab(tab: 'overview' | 'ledger') {
  activeTab.value = tab
  void router.replace({ query: { ...route.query, tab } })
}

function openLedgerWithFilter(statusFilter = '全部') {
  ledgerFilter.value = statusFilter
  switchTab('ledger')
}

function handleReadinessClick(params: { name?: string }) {
  const filters: Record<string, string> = {
    已导入: '已上线',
    已校验: '已上线',
    收集中: '建设中',
    未收集: '准备中',
  }
  if (params.name && filters[params.name]) openLedgerWithFilter(filters[params.name])
}

const format = (value: number | undefined) => (
  value === undefined ? '—' : new Intl.NumberFormat('zh-CN').format(value)
)

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

const stageDistributionOption = computed(() => createTaskStageOverviewOption(buildTaskStageSeries(taskStages.value)))
const trainingConversionOption = computed(() => createTrainingConversionOption(trainingSummary.value?.byType ?? []))
const trainingMixOption = computed(() => createTrainingMixOption(trainingSummary.value?.byType ?? []))
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
      <!-- B2: 100% 纵向构成柱在有限面积内保留 8 阶段，避免横向长条形成线墙 -->
      <CockpitPanel title="阶段任务结构" zone="B2" subtitle="各阶段任务完成、推进与待启动占比" class="col-span-8">
        <VChart class="w-full h-full min-h-0" :option="stageDistributionOption" autoresize />
      </CockpitPanel>

      <!-- B3: 省域建设排行 -->
      <CockpitPanel title="省域建设领先榜" zone="B3" subtitle="完成率前八" class="col-span-4">
        <StatList :rows="rankRows" ranked density="dense" scroll />
      </CockpitPanel>

      <!-- B4: 培训分类转化、场次构成与总体漏斗三图，充分利用主分析面积 -->
      <CockpitPanel title="培训赋能全景" zone="B4" subtitle="分类人次转化、场次构成与总体认证漏斗" class="col-span-8">
        <div class="grid grid-cols-12 gap-3 h-full min-h-0">
          <section class="col-span-7 flex flex-col min-h-0 rounded-xl bg-surface-veil-03 border border-surface-veil-06 p-2">
            <div class="flex items-center justify-between pb-1.5 border-b border-surface-veil-06 text-cockpit-xs">
              <span class="font-medium text-slate-300">四类培训人次转化</span>
              <span class="font-mono text-slate-500">16 项真实指标</span>
            </div>
            <VChart class="w-full flex-1 min-h-0" :option="trainingConversionOption" autoresize />
          </section>
          <div class="col-span-5 grid grid-rows-2 gap-2 min-h-0">
            <section class="flex flex-col min-h-0 rounded-xl bg-surface-veil-03 border border-surface-veil-06 p-2">
              <div class="flex items-center justify-between pb-1 border-b border-surface-veil-06 text-cockpit-xs">
                <span class="font-medium text-slate-300">培训场次构成</span>
                <span class="font-mono text-sky-400">{{ format(trainingSummary?.totalSessions) }} 场</span>
              </div>
              <VChart class="w-full flex-1 min-h-0" :option="trainingMixOption" autoresize />
            </section>
            <section class="flex flex-col min-h-0 rounded-xl bg-surface-veil-03 border border-surface-veil-06 p-2">
              <div class="flex items-center justify-between pb-1 border-b border-surface-veil-06 text-cockpit-xs">
                <span class="font-medium text-slate-300">总体参培与认证漏斗</span>
                <span class="font-mono text-emerald-400">通过 {{ format(trainingSummary?.totalPassed) }} 人</span>
              </div>
              <VChart class="w-full flex-1 min-h-0" :option="trainingFunnelOption" autoresize />
            </section>
          </div>
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
          <p class="text-center text-cockpit-xs text-slate-500 flex-shrink-0">点击扇区，按状态进入单位台账</p>
        </div>
      </CockpitPanel>
    </main>

    <!-- 并入的数据准备台账下钻主区 -->
    <main v-else class="flex-1 min-h-0 flex flex-col">
      <ConstructionLedger :initial-filter="ledgerFilter" @back="switchTab('overview')" />
    </main>
  </div>
</template>
