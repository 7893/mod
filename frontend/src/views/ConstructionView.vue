<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import {
  Award,
  BookOpen,
  CheckCircle2,
  Database,
  Users,
} from 'lucide-vue-next'
import CockpitPanel from '../components/CockpitPanel.vue'
import ConstructionLedger from '../components/ConstructionLedger.vue'
import MetricGrid from '../components/blocks/MetricGrid.vue'
import StatList from '../components/blocks/StatList.vue'
import type { MetricItem, StatRow } from '../components/blocks/types.ts'
import {
  calmAnimation,
  chartInk,
  chartPalette,
  chartTooltip,
  valueAxis,
} from '../charts/theme.ts'
import { buildTaskStageSeries } from '../charts/panelData.ts'
import { createTaskStageOption } from '../charts/panelOptions.ts'
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

const format = (value: number | undefined) => (
  value === undefined ? '—' : new Intl.NumberFormat('zh-CN').format(value)
)

const taskStages = computed(() => store.snapshot.construction?.taskStages || [])

const constructionSummary = computed(() => store.snapshot.construction)
const trainingSummary = computed(() => constructionSummary.value?.trainingSummary)
const readinessSummary = computed(() => constructionSummary.value?.dataReadinessSummary)

const summaryItems = computed<MetricItem[]>(() => [
  {
    label: '综合完成率',
    value: constructionSummary.value?.avgProgress ?? '—',
    unit: constructionSummary.value ? '%' : undefined,
    tone: 'accent',
    hint: '全量建设任务平均进度',
  },
  {
    label: '任务总数',
    value: format(constructionSummary.value?.totalTasks),
    unit: constructionSummary.value ? '项' : undefined,
    hint: `${format(store.snapshot.overview.orgTotal)} 家纳管单位`,
  },
  {
    label: '已完成',
    value: format(constructionSummary.value?.completedTasks),
    unit: constructionSummary.value ? '项' : undefined,
    tone: 'success',
    hint: '已通过阶段验收',
  },
  {
    label: '进行中',
    value: format(constructionSummary.value?.inProgressTasks),
    unit: constructionSummary.value ? '项' : undefined,
    tone: 'warning',
    hint: '当前正在推进',
  },
])

const RANK_LIMIT = 10

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

const trainingItems = computed<MetricItem[]>(() => [
  { label: '培训场次', value: format(trainingSummary.value?.totalSessions), icon: BookOpen },
  { label: '参培人次', value: format(trainingSummary.value?.totalActual), icon: Users },
  {
    label: '考核通过',
    value: format(trainingSummary.value?.totalPassed),
    icon: CheckCircle2,
    tone: 'accent',
  },
  {
    label: '证书发放',
    value: format(trainingSummary.value?.totalCert),
    icon: Award,
    tone: 'success',
  },
])

// 色值统一取自 charts/theme.ts
const chartColors = {
  accent: chartPalette.accent,
  success: chartPalette.success,
  warning: chartPalette.warning,
  muted: chartPalette.neutral,
  textMuted: chartInk.textMuted,
}

const stageDistributionOption = computed(() => createTaskStageOption(buildTaskStageSeries(taskStages.value)))

// B4 培训分类横向柱状图：展示4大培训类型通过率与规模
const trainingBarOption = computed(() => {
  const list = [...(trainingSummary.value?.byType ?? [])].reverse()
  return {
    ...calmAnimation,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      ...chartTooltip,
      formatter: (params: any) => {
        const p = Array.isArray(params) ? params[0] : params
        const raw = list[p?.dataIndex]
        if (!raw) return ''
        const rate = raw.actual ? ((raw.passed / raw.actual) * 100).toFixed(1) : '—'
        return `
          <div style="font-size: 12px; line-height: 1.6;">
            <div style="font-weight: 600; color: #f1f5f9; margin-bottom: 4px;">${raw.type}</div>
            <div style="color: #94a3b8;">培训场次: <b style="color: #f1f5f9; font-family: monospace;">${raw.count?.toLocaleString()} 场</b></div>
            <div style="color: #94a3b8;">实参培人数: <b style="color: #f1f5f9; font-family: monospace;">${raw.actual?.toLocaleString()} 人</b> (应参培 ${raw.expected?.toLocaleString()} 人)</div>
            <div style="color: #94a3b8;">考核通过率: <b style="color: #34d399; font-family: monospace;">${rate}%</b> (${raw.passed?.toLocaleString()} 人)</div>
            ${raw.cert ? `<div style="color: #94a3b8;">证书发放: <b style="color: #38bdf8; font-family: monospace;">${raw.cert?.toLocaleString()} 张</b></div>` : ''}
          </div>
        `
      },
    },
    grid: { top: 12, bottom: 20, left: 160, right: 65 },
    xAxis: {
      ...valueAxis,
      max: 100,
      splitNumber: 4,
      axisLabel: { color: '#64748b', fontSize: 10, fontFamily: 'monospace', formatter: '{value}%' },
      splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)', type: 'dashed' } },
    },
    yAxis: {
      type: 'category',
      data: list.map((i) => i.type),
      axisLabel: { color: '#94a3b8', fontSize: 11 },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.08)' } },
    },
    series: [{
      name: '考核通过率',
      type: 'bar',
      barWidth: 14,
      data: list.map((i) => {
        const rate = i.actual ? Number(((i.passed / i.actual) * 100).toFixed(1)) : 0
        return {
          value: rate,
          itemStyle: {
            borderRadius: [0, 4, 4, 0],
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 1, y2: 0,
              colorStops: [
                { offset: 0, color: 'rgba(56, 189, 248, 0.25)' },
                { offset: 1, color: '#38bdf8' },
              ],
            },
          },
        }
      }),
      label: {
        show: true,
        position: 'right',
        color: '#34d399',
        fontFamily: 'monospace',
        fontSize: 11,
        fontWeight: 'bold',
        formatter: '{c}%',
      },
      showBackground: true,
      backgroundStyle: {
        color: 'rgba(255, 255, 255, 0.03)',
        borderRadius: [0, 4, 4, 0],
      },
    }],
  }
})

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
      { value: readinessSummary.value?.imported ?? 0, name: `已导入 (${format(readinessSummary.value?.imported)})`, itemStyle: { color: chartColors.accent } },
      { value: readinessSummary.value?.verified ?? 0, name: `已校验 (${format(readinessSummary.value?.verified)})`, itemStyle: { color: chartColors.success } },
      { value: readinessSummary.value?.collecting ?? 0, name: `收集中 (${format(readinessSummary.value?.collecting)})`, itemStyle: { color: chartColors.warning } },
      { value: readinessSummary.value?.notCollected ?? 0, name: `未收集 (${format(readinessSummary.value?.notCollected)})`, itemStyle: { color: chartColors.muted } },
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
      <MetricGrid :items="summaryItems" variant="inline" :columns="4" />
    </CockpitPanel>

    <!-- 建设全景主区 -->
    <main v-if="activeTab === 'overview'" class="flex-1 min-h-0 grid grid-cols-construction grid-rows-construction gap-2.5">
      <!-- B2: 以堆叠图承载 8 阶段，避免小卡横向拥挤 -->
      <CockpitPanel title="阶段任务分布" zone="B2" subtitle="已完成 / 进行中 / 未开始 · 右侧为阶段完成率" class="col-span-2">
        <VChart class="w-full h-full min-h-0" :option="stageDistributionOption" autoresize />
      </CockpitPanel>

      <!-- B3: 省域建设排行 -->
      <CockpitPanel title="省域建设排行" zone="B3" subtitle="完成率前十">
        <StatList :rows="rankRows" ranked density="dense" scroll />
      </CockpitPanel>

      <!-- B4: 培训赋能 (去掉报表表格，替换为可视化横向柱状图，B-3) -->
      <CockpitPanel title="培训赋能" zone="B4" subtitle="场次、参培与认证" class="col-span-2">
        <div class="flex h-full min-h-0 flex-col gap-2">
          <MetricGrid :items="trainingItems" variant="inline" :columns="4" />
          <div class="flex-1 min-h-0">
            <VChart class="w-full h-full" :option="trainingBarOption" autoresize />
          </div>
        </div>
      </CockpitPanel>

      <!-- B5: 期初数据准备度 (保留台账下钻入口与状态过滤卡片) -->
      <CockpitPanel title="期初数据准备度" zone="B5" subtitle="单位数据状态">
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
          <VChart class="min-h-0 flex-1" :option="readinessPieOption" autoresize />
          <div class="grid grid-cols-2 gap-2 text-cockpit-sm">
            <button
              type="button"
              class="flex justify-between rounded-lg bg-surface-veil-03 px-2.5 py-1.5 text-left hover:bg-white/5 transition-colors cursor-pointer"
              title="点击查看已导入单位台账"
              @click="openLedgerWithFilter('已上线')"
            >
              <span class="text-slate-400">已导入</span>
              <b class="font-mono text-sky-400">{{ format(readinessSummary?.imported) }} 家</b>
            </button>
            <button
              type="button"
              class="flex justify-between rounded-lg bg-surface-veil-03 px-2.5 py-1.5 text-left hover:bg-white/5 transition-colors cursor-pointer"
              title="点击查看已校验单位台账"
              @click="openLedgerWithFilter('已上线')"
            >
              <span class="text-slate-400">已校验</span>
              <b class="font-mono text-emerald-400">{{ format(readinessSummary?.verified) }} 家</b>
            </button>
            <button
              type="button"
              class="flex justify-between rounded-lg bg-surface-veil-03 px-2.5 py-1.5 text-left hover:bg-white/5 transition-colors cursor-pointer"
              title="点击查看收集中单位台账"
              @click="openLedgerWithFilter('建设中')"
            >
              <span class="text-slate-400">收集中</span>
              <b class="font-mono text-amber-400">{{ format(readinessSummary?.collecting) }} 家</b>
            </button>
            <button
              type="button"
              class="flex justify-between rounded-lg bg-surface-veil-03 px-2.5 py-1.5 text-left hover:bg-white/5 transition-colors cursor-pointer"
              title="点击查看未收集单位台账"
              @click="openLedgerWithFilter('准备中')"
            >
              <span class="text-slate-400">未收集</span>
              <b class="font-mono text-slate-300">{{ format(readinessSummary?.notCollected) }} 家</b>
            </button>
          </div>
        </div>
      </CockpitPanel>
    </main>

    <!-- 并入的数据准备台账下钻主区 -->
    <main v-else class="flex-1 min-h-0 flex flex-col">
      <ConstructionLedger :initial-filter="ledgerFilter" @back="switchTab('overview')" />
    </main>
  </div>
</template>
