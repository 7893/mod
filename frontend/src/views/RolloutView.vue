<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, GaugeChart, HeatmapChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent, VisualMapComponent } from 'echarts/components'
import CockpitPanel from '../components/CockpitPanel.vue'
import CommandBand from '../components/blocks/CommandBand.vue'
import EmptyNote from '../components/blocks/EmptyNote.vue'
import StatList from '../components/blocks/StatList.vue'
import ChartCanvas from '../components/charts/ChartCanvas.vue'
import type { MetricItem, StatRow } from '../components/blocks/types.ts'
import RolloutLedgerTable from '../components/RolloutLedgerTable.vue'
import { buildCoverageComposition } from '../charts/panelData.ts'
import { createCoverageOption } from '../charts/panelOptions.ts'
import {
  createRolloutCommandOption,
  createRolloutTrendMatrixOption,
} from '../charts/rolloutOptions.ts'
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
    .sort((a, b) => b.unlaunched - a.unlaunched || a.launchedPct - b.launchedPct || a.name.localeCompare(b.name, 'zh-CN'))
})

const backlogProvinces = computed(() => provinceRolloutRanking.value.slice(0, 3))

const currentBatchRows = computed<StatRow[]>(() => [...batches.value]
  .map((batch) => ({ ...batch, pending: Math.max(0, batch.total - batch.launched - batch.dual) }))
  .sort((left, right) => right.pending - left.pending || left.batchId - right.batchId)
  .slice(0, 5)
  .map((batch) => ({
    id: batch.batchId,
    label: batch.name,
    sub: `总 ${format(batch.total)} · 待推进 ${format(batch.pending)}`,
    value: format(batch.launched),
    unit: '家上线',
    progress: batch.launchedPct,
    progressAlt: batch.total > 0 ? Math.round((batch.dual * 1000) / batch.total) / 10 : 0,
    progressLabel: '上线率',
    progressAltLabel: '双轨率',
    tone: batch.launchedPct < 50 ? 'warning' : 'success',
  })))

const provinceBacklogRows = computed<StatRow[]>(() => {
  const max = Math.max(1, ...backlogProvinces.value.map((province) => province.unlaunched))
  return backlogProvinces.value.map((province) => ({
    id: province.name,
    label: province.name,
    sub: `上线率 ${province.launchedPct}%`,
    value: province.unlaunched,
    unit: '家待推进',
    progress: (province.unlaunched * 100) / max,
    tone: 'warning',
  }))
})

const coveredProvinceCount = computed(() => new Set(store.provinceSummary.map((p) => p.name)).size)

const commandFacts = computed<MetricItem[]>(() => [
  { label: '纳管单位', value: format(store.snapshot.overview.orgTotal) },
  { label: '已上线', value: format(store.snapshot.overview.launched), unit: '家', tone: 'success' },
  { label: '双轨运行', value: format(store.snapshot.overview.dual), unit: '家', tone: 'warning' },
  { label: '推广范围', value: `${batches.value.length} 批 / ${coveredProvinceCount.value} 省`, tone: 'accent' },
])

const contactFacts = computed<StatRow[]>(() => [
  { label: '联系人总数', value: format(store.snapshot.overview.contactsTotal), tone: 'accent' },
  { label: '已覆盖单位', value: format(contactCoverage.value?.covered), tone: 'success' },
  { label: '待补齐缺口', value: format(contactCoverage.value?.gap), tone: 'warning' },
])

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
          <ChartCanvas :option="rolloutCommandOption" />
        </template>
      </CommandBand>
    </CockpitPanel>

    <div class="grid grid-rows-rollout-body gap-2.5 flex-1 min-h-0">
      <!-- C2 同屏表达批次当前态与历史态；C3/C4 只展示缺口与例外 -->
      <div class="grid grid-cols-rollout-analysis grid-rows-rollout-analysis gap-2.5 min-h-0">
        <CockpitPanel title="批次推进全景" zone="C2" subtitle="左看当前缺口，右看历史爬坡" class="col-span-8 row-span-2">
          <div class="grid grid-cols-12 gap-3 h-full min-h-0">
            <section class="col-span-5 flex flex-col min-h-0 pr-3 border-r border-surface-veil-06">
              <span class="text-cockpit-xs text-slate-500 flex-shrink-0">当前待推进最多五批</span>
              <StatList class="flex-1" :rows="currentBatchRows" flat density="dense" />
            </section>
            <section class="col-span-7 flex flex-col min-h-0">
              <span class="text-cockpit-xs text-slate-500 flex-shrink-0">历史上线率与双轨率</span>
              <ChartCanvas
                class="flex-1"
                :option="rolloutTrendOption"
                :empty="rolloutTrend.length === 0"
                empty-text="暂无批次历史快照"
              />
            </section>
          </div>
        </CockpitPanel>

        <CockpitPanel title="省域推进缺口" zone="C3" subtitle="待推进单位最多三省" class="col-span-4 min-h-0">
          <StatList :rows="provinceBacklogRows" ranked density="dense" />
        </CockpitPanel>

        <CockpitPanel title="联系人覆盖例外" zone="C4" subtitle="只在存在缺口时展示分布" class="col-span-4 min-h-0">
          <div v-if="contactCoverage && contactCoverage.gap > 0" class="grid grid-cols-5 h-full min-h-0 gap-2 items-center">
            <ChartCanvas class="col-span-2" :option="contactCoverageOption" />
            <StatList class="col-span-3 self-stretch" :rows="contactFacts" flat density="dense" />
          </div>
          <EmptyNote v-else>{{ contactCoverage ? `全部 ${format(contactCoverage.covered)} 家单位已完成联系人覆盖` : '暂无联系人覆盖数据' }}</EmptyNote>
        </CockpitPanel>
      </div>

      <!-- C5: 单位台账表格与分页组件 -->
      <RolloutLedgerTable />
    </div>
  </div>
</template>
