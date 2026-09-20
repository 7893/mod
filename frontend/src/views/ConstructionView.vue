<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, HeatmapChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent, VisualMapComponent } from 'echarts/components'
import { Database } from 'lucide-vue-next'
import CockpitPanel from '../components/CockpitPanel.vue'
import ConstructionLedger from '../components/ConstructionLedger.vue'
import DrawerShell from '../components/DrawerShell.vue'
import PanelLegend from '../components/PanelLegend.vue'
import OverviewBand from '../components/blocks/OverviewBand.vue'
import StatList from '../components/blocks/StatList.vue'
import ChartCanvas from '../components/charts/ChartCanvas.vue'
import type { StatRow } from '../components/blocks/types.ts'
import { buildOverviewComposition, buildTaskStageSeries } from '../charts/panelData.ts'
import {
  createLaunchGateOption,
  createReadinessPieOption,
  createTaskStageMatrixOption,
  createTrainingFunnelOption,
} from '../charts/constructionOptions.ts'
import { formatCount as format, formatPercent } from '../formatters/metrics.ts'
import { useProjectStore } from '../stores/project.ts'

use([
  CanvasRenderer,
  BarChart,
  HeatmapChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  VisualMapComponent,
])

const route = useRoute()
const router = useRouter()
const store = useProjectStore()
const ledgerOpen = ref(route.query.tab === 'ledger')
const ledgerStatusFilter = ref('全部')
const ledgerReadinessFilter = ref('全部')

watch(() => route.query.tab, (value) => {
  ledgerOpen.value = value === 'ledger'
})

function setLedgerOpen(open: boolean) {
  ledgerOpen.value = open
  const query = { ...route.query }
  if (open) query.tab = 'ledger'
  else delete query.tab
  void router.replace({ query })
}

function openLedgerWithFilter(statusFilter = '全部') {
  ledgerStatusFilter.value = statusFilter
  ledgerReadinessFilter.value = '全部'
  setLedgerOpen(true)
}

function handleReadinessClick(params: { name?: string }) {
  if (!params.name || !['已导入', '已校验', '收集中', '未收集'].includes(params.name)) return
  ledgerStatusFilter.value = '全部'
  ledgerReadinessFilter.value = params.name
  setLedgerOpen(true)
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

const laggingProvinces = computed(() =>
  [...store.provinceSummary].sort((a, b) => a.value - b.value).slice(0, 8),
)

const laggingRows = computed<StatRow[]>(() =>
  laggingProvinces.value.map((province) => ({
    id: province.name,
    label: province.name,
    value: province.value,
    unit: '%',
    progress: province.value,
    tone: province.value < 80 ? 'warning' : 'default',
  })),
)

const stageSeries = computed(() => buildTaskStageSeries(taskStages.value))
const stageMatrixOption = computed(() => createTaskStageMatrixOption(stageSeries.value))
const launchGateStages = computed(() => stageSeries.value.filter((stage) => (
  ['期初数据', '接口联调', '双轨验证', '用户培训'].includes(stage.name)
)))
const launchGateOption = computed(() => createLaunchGateOption(launchGateStages.value))
const trainingFunnelOption = computed(() => createTrainingFunnelOption(trainingSummary.value))
const readinessPieOption = computed(() => createReadinessPieOption(readinessSummary.value))

const readinessPriority: Record<string, number> = {
  未收集: 0,
  收集中: 1,
  已导入: 2,
  已校验: 3,
}

const ledgerPreviewRows = computed(() => [...store.entities]
  .sort((left, right) => {
    const readiness = (readinessPriority[left.readinessStatus || ''] ?? -1) - (readinessPriority[right.readinessStatus || ''] ?? -1)
    return readiness || left.construction - right.construction
  })
  .slice(0, 3))
</script>

<template>
  <div class="w-full h-full p-3 bg-surface-base flex flex-col gap-2.5 overflow-hidden" data-zone="B">
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

    <main class="flex-1 min-h-0 grid grid-cols-construction grid-rows-construction gap-2.5">
      <CockpitPanel title="建设阶段作战矩阵" zone="B2" subtitle="八阶段任务状态与完成度，单一矩阵表达" class="col-span-8 min-h-0">
        <template #actions>
          <PanelLegend compact :items="[
            { label: '已完成', tone: 'success' },
            { label: '进行中', tone: 'accent' },
            { label: '待启动', tone: 'neutral' },
          ]" />
        </template>
        <ChartCanvas :option="stageMatrixOption" />
      </CockpitPanel>

      <CockpitPanel title="省域建设滞后榜" zone="B3" subtitle="完成率后八 · 优先识别建设短板" class="col-span-4">
        <StatList :rows="laggingRows" ranked density="dense" scroll />
      </CockpitPanel>

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
            <ChartCanvas
              class="flex-1"
              :option="launchGateOption"
              :empty="launchGateStages.length === 0"
              empty-text="暂无关键门禁任务数据"
            />
          </section>
          <section class="col-span-4 flex flex-col min-h-0">
            <div class="flex items-center justify-between pb-1 text-cockpit-xs">
              <span class="font-medium text-slate-300">参培认证漏斗</span>
              <span class="font-mono text-emerald-400">通过 {{ format(trainingSummary?.totalPassed) }} 人</span>
            </div>
            <ChartCanvas
              class="flex-1"
              :option="trainingFunnelOption"
              :empty="!trainingSummary"
              empty-text="暂无培训转化数据"
            />
          </section>
        </div>
      </CockpitPanel>

      <CockpitPanel title="期初数据准备度" zone="B5" subtitle="单位数据状态" class="col-span-4">
        <template #actions>
          <button
            type="button"
            class="flex items-center gap-1.5 px-2.5 py-1 rounded bg-sky-500/15 text-sky-400 border border-sky-500/30 hover:bg-sky-500/25 transition-colors text-cockpit-xs font-medium cursor-pointer"
            @click="openLedgerWithFilter('全部')"
          >
            <Database :size="12" />
            <span>完整台账</span>
          </button>
        </template>
        <ChartCanvas class="flex-1 cursor-pointer" :option="readinessPieOption" @chart-click="handleReadinessClick" />
      </CockpitPanel>

      <CockpitPanel title="建设台账预览" zone="B6" subtitle="优先显示准备度和建设进度最低单位" class="col-span-12 min-h-0">
        <template #actions>
          <button type="button" class="text-cockpit-sm text-sky-400 hover:text-sky-300 cursor-pointer" @click="openLedgerWithFilter('全部')">
            打开筛选与调态台账
          </button>
        </template>
        <div class="flex-1 min-h-0 overflow-hidden rounded-lg border border-surface-veil-06">
          <table class="w-full h-full table-fixed border-collapse text-cockpit-xs text-left">
            <thead class="bg-surface-veil-03 text-slate-500">
              <tr>
                <th class="px-3 py-1.5 w-2/5">单位</th>
                <th class="px-3 py-1.5">省域</th>
                <th class="px-3 py-1.5">推进状态</th>
                <th class="px-3 py-1.5 text-right">建设进度</th>
                <th class="px-3 py-1.5 text-right">期初数据</th>
                <th class="px-3 py-1.5 text-right">凭证率</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-surface-veil-06">
              <tr v-for="row in ledgerPreviewRows" :key="row.id" class="text-slate-300">
                <td class="px-3 py-1 truncate" :title="row.name">{{ row.name }}</td>
                <td class="px-3 py-1">{{ row.province }}</td>
                <td class="px-3 py-1">{{ row.status }}</td>
                <td class="px-3 py-1 text-right font-mono text-sky-400">{{ row.construction }}%</td>
                <td class="px-3 py-1 text-right"><span class="text-amber-400">{{ row.readinessStatus || '未提供' }}</span> · {{ row.openingData }}%</td>
                <td class="px-3 py-1 text-right font-mono">{{ formatPercent(row.voucherRate) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </CockpitPanel>
    </main>

    <DrawerShell v-if="ledgerOpen" label="建设与期初数据完整台账" size="wide" @close="setLedgerOpen(false)">
      <ConstructionLedger
        :initial-filter="ledgerStatusFilter"
        :initial-readiness-filter="ledgerReadinessFilter"
        @back="setLedgerOpen(false)"
      />
    </DrawerShell>
  </div>
</template>
