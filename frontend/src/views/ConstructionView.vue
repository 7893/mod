<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import {
  Award,
  BookOpen,
  CheckCircle2,
  Users,
} from 'lucide-vue-next'
import CockpitPanel from '../components/CockpitPanel.vue'
import MetricGrid from '../components/blocks/MetricGrid.vue'
import StatList from '../components/blocks/StatList.vue'
import type { MetricItem, StatRow } from '../components/blocks/types.ts'
import { chartInk, chartPalette, chartTooltip } from '../charts/theme.ts'
import { useProjectStore } from '../stores/project.ts'

use([CanvasRenderer, PieChart, TooltipComponent, LegendComponent])

const store = useProjectStore()
const format = (value: number | undefined) => (
  value === undefined ? '—' : new Intl.NumberFormat('zh-CN').format(value)
)

const taskStages = computed(() => store.snapshot.construction?.taskStages || [])

const stageItems = computed<MetricItem[]>(() =>
  taskStages.value.map((stg) => ({
    label: stg.name,
    value: stg.avgProgress,
    unit: '%',
    progress: stg.avgProgress,
    meta: [
      { label: '总', value: stg.total },
      { label: '完', value: stg.completed },
      { label: '行', value: stg.inProgress },
    ],
  })),
)
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
 * 排行条的条长映射。
 *
 * 进入榜单的各省完成率集中在几个百分点的窄区间内，若条长直接等于百分比，
 * 第 1 名和第 10 名的条几乎一样长，排行就失去了可比性。
 * 这里把区间拉伸到 [34%, 100%]，保留排序直觉又放大差距；
 * 具体数值仍以条末的百分比文字为准。
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

// 色值统一取自 charts/theme.ts，避免图表区与页面外壳出现两套蓝绿黄
const chartColors = {
  accent: chartPalette.accent,
  success: chartPalette.success,
  warning: chartPalette.warning,
  muted: chartPalette.neutral,
  textMuted: chartInk.textMuted,
}

const readinessPieOption = computed(() => ({
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
    <CockpitPanel
      title="系统建设进度全景"
      zone="B1"
      :subtitle="`${format(store.snapshot.overview.orgTotal)} 家单位 · ${format(constructionSummary?.totalTasks)} 项任务 · ${format(trainingSummary?.totalSessions)} 场培训`"
      class="flex-shrink-0"
    >
      <MetricGrid :items="summaryItems" variant="inline" :columns="4" />
    </CockpitPanel>

    <main class="flex-1 min-h-0 grid grid-cols-construction grid-rows-construction gap-2.5">
      <CockpitPanel title="阶段任务分布" zone="B2" subtitle="按建设阶段汇总" class="col-span-2">
        <MetricGrid :items="stageItems" :max-per-row="4" size="sm" fill />
      </CockpitPanel>

      <CockpitPanel title="省域建设排行" zone="B3" subtitle="完成率前十">
        <StatList :rows="rankRows" ranked density="dense" scroll />
      </CockpitPanel>

      <CockpitPanel title="培训赋能" zone="B4" subtitle="场次、参培与认证" class="col-span-2">
        <div class="flex h-full min-h-0 flex-col gap-2.5">
          <MetricGrid :items="trainingItems" variant="inline" :columns="4" />

          <div class="flex-1 min-h-0 overflow-y-auto rounded-xl border border-surface-veil-06 bg-surface-veil-03">
            <table class="w-full border-collapse text-cockpit-sm">
              <thead>
                <tr>
                  <th class="sticky top-0 bg-slate-900 px-3 py-2 text-left font-medium text-slate-400">培训类型</th>
                  <th class="sticky top-0 bg-slate-900 px-3 py-2 text-right font-medium text-slate-400">场次</th>
                  <th class="sticky top-0 bg-slate-900 px-3 py-2 text-right font-medium text-slate-400">应参培</th>
                  <th class="sticky top-0 bg-slate-900 px-3 py-2 text-right font-medium text-slate-400">实参培</th>
                  <th class="sticky top-0 bg-slate-900 px-3 py-2 text-right font-medium text-slate-400">通过率</th>
                  <th class="sticky top-0 bg-slate-900 px-3 py-2 text-right font-medium text-slate-400">证书</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="t in trainingSummary?.byType ?? []"
                  :key="t.type"
                  class="border-t border-surface-veil-06 text-slate-200"
                >
                  <td class="px-3 py-2 font-medium">{{ t.type }}</td>
                  <td class="px-3 py-2 text-right font-mono">{{ format(t.count) }}</td>
                  <td class="px-3 py-2 text-right font-mono">{{ format(t.expected) }}</td>
                  <td class="px-3 py-2 text-right font-mono">{{ format(t.actual) }}</td>
                  <td class="px-3 py-2 text-right font-mono text-emerald-400">
                    {{ t.actual ? `${((t.passed / t.actual) * 100).toFixed(1)}%` : '—' }}
                  </td>
                  <td class="px-3 py-2 text-right font-mono">{{ format(t.cert) }}</td>
                </tr>
                <tr v-if="!trainingSummary?.byType?.length">
                  <td colspan="6" class="px-3 py-6 text-center text-slate-500">培训分类数据未提供</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </CockpitPanel>

      <CockpitPanel title="期初数据准备度" zone="B5" subtitle="单位数据状态">
        <div class="flex h-full min-h-0 flex-col gap-2">
          <VChart class="min-h-0 flex-1" :option="readinessPieOption" autoresize />
          <div class="grid grid-cols-2 gap-2 text-cockpit-sm">
            <div class="flex justify-between rounded-lg bg-surface-veil-03 px-2.5 py-1.5">
              <span class="text-slate-400">已导入</span>
              <b class="font-mono text-sky-400">{{ format(readinessSummary?.imported) }} 家</b>
            </div>
            <div class="flex justify-between rounded-lg bg-surface-veil-03 px-2.5 py-1.5">
              <span class="text-slate-400">已校验</span>
              <b class="font-mono text-emerald-400">{{ format(readinessSummary?.verified) }} 家</b>
            </div>
            <div class="flex justify-between rounded-lg bg-surface-veil-03 px-2.5 py-1.5">
              <span class="text-slate-400">收集中</span>
              <b class="font-mono text-amber-400">{{ format(readinessSummary?.collecting) }} 家</b>
            </div>
            <div class="flex justify-between rounded-lg bg-surface-veil-03 px-2.5 py-1.5">
              <span class="text-slate-400">未收集</span>
              <b class="font-mono text-slate-300">{{ format(readinessSummary?.notCollected) }} 家</b>
            </div>
          </div>
        </div>
      </CockpitPanel>
    </main>
  </div>
</template>
