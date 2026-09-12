<script setup lang="ts">
import { computed } from 'vue'
import { ArrowRight, Check, FileCheck2, Scale, ServerCog, Workflow } from 'lucide-vue-next'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, GaugeChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import CockpitPanel from '../components/CockpitPanel.vue'
import PanelLegend from '../components/PanelLegend.vue'
import CommandBand from '../components/blocks/CommandBand.vue'
import ChartFacts from '../components/blocks/ChartFacts.vue'
import EmptyNote from '../components/blocks/EmptyNote.vue'
import MetricGrid from '../components/blocks/MetricGrid.vue'
import StatList from '../components/blocks/StatList.vue'
import type { BlockTone, MetricItem, StatRow } from '../components/blocks/types.ts'
import { formatCount, formatPercent } from '../formatters/metrics.ts'
import { useProjectStore } from '../stores/project.ts'
import {
  calcDualRunConsistency,
  buildQualityAuditList,
  type QualityAuditItem,
} from '../utils/qualityMetrics.ts'
import {
  createDualRunOutcomeOption,
  createIntegrationOutcomeOption,
  createOperationsOverviewOption,
  createOperationsTrendOption,
  createQualityAuditVolumeOption,
  createVoucherQualityOption,
} from '../charts/operationsOptions.ts'

use([CanvasRenderer, BarChart, GaugeChart, LineChart, GridComponent, TooltipComponent])

const store = useProjectStore()
const format = formatCount

const ops = computed(() => store.snapshot.operations)

const flowSteps = computed(() => [
  { label: '业务单据', value: `${format(ops.value.businessDocument)} 笔`, icon: Check, status: 'done' },
  { label: '单据明细', value: `${format(ops.value.businessDocumentLine)} 行`, icon: Check, status: 'done' },
  { label: '会计凭证', value: `${format(ops.value.accountingVoucher)} 张`, icon: FileCheck2, status: 'done' },
  { label: '会计分录', value: `${format(ops.value.accountingVoucherLine)} 条`, icon: ServerCog, status: 'done' },
  { label: '接口集成', value: `${format(ops.value.integrationResult)} 笔`, icon: Workflow, status: 'active' },
  { label: '双轨核对', value: `${format(ops.value.dualRunResult)} 笔`, icon: Scale, status: 'active' },
])

const integrationTotal = computed(() => ops.value.integrationResult || 0)
const operationsOverviewOption = computed(() => createOperationsOverviewOption(ops.value))
const operationsTrend = computed(() => store.snapshot.operationsTrend ?? [])
const operationsTrendOption = computed(() => createOperationsTrendOption(operationsTrend.value))
const documentLineRatio = computed(() => (
  ops.value.businessDocument && ops.value.businessDocumentLine != null
    ? (ops.value.businessDocumentLine / ops.value.businessDocument).toFixed(2)
    : '—'
))
const voucherQualityOption = computed(() => createVoucherQualityOption(
  store.snapshot.overview.voucherSuccessPct,
  ops.value.accountingVoucher,
  ops.value.accountingVoucherLine,
))
const averageVoucherLines = computed(() => (
  ops.value.accountingVoucher
    ? (ops.value.accountingVoucherLine / ops.value.accountingVoucher).toFixed(2)
    : '—'
))
const integrationRate = computed<number | null>(() => {
  const explicitRate = store.snapshot.overview.integrationSuccessPct
  if (explicitRate != null && Number.isFinite(Number(explicitRate))) return Number(explicitRate)
  if (integrationTotal.value > 0 && ops.value.integrationSuccess != null) {
    return (ops.value.integrationSuccess * 100) / integrationTotal.value
  }
  return null
})
const integrationSuccessCount = computed<number | null>(() => {
  if (ops.value.integrationSuccess != null) return ops.value.integrationSuccess
  if (integrationRate.value == null || integrationTotal.value <= 0) return null
  return Math.round((integrationTotal.value * integrationRate.value) / 100)
})
const integrationFailedCount = computed<number | null>(() => {
  if (ops.value.integrationFailed != null) return ops.value.integrationFailed
  if (integrationSuccessCount.value == null) return null
  return Math.max(0, integrationTotal.value - integrationSuccessCount.value)
})
const integrationOutcomeOption = computed(() => createIntegrationOutcomeOption(
  integrationSuccessCount.value,
  integrationFailedCount.value,
))

const dualRunStats = computed(() => {
  return calcDualRunConsistency(
    ops.value.dualRunResult,
    ops.value.dualRunConsistent,
    ops.value.dualRunInconsistent,
  )
})

const dualRunOutcomeOption = computed(() => dualRunStats.value
  ? createDualRunOutcomeOption(dualRunStats.value.consistent, dualRunStats.value.inconsistent)
  : null)

const dualRunPass = computed(() => (
  dualRunStats.value
    ? dualRunStats.value.consistencyPct >= store.snapshot.businessRules.lifecycle.dualRunConsistencyRateMin
    : null
))

const dualRunConsistencyRateMin = computed(() => (
  store.snapshot.businessRules.lifecycle.dualRunConsistencyRateMin
))

const dualRunBreakdown = computed(() => {
  return store.snapshot.operations?.dualRunBreakdown || []
})

const qualityAuditList = computed(() => {
  return buildQualityAuditList(
    store.snapshot.quality,
    ops.value,
    store.snapshot.overview.orgTotal,
  )
})

const scaleFacts = computed<MetricItem[]>(() => {
  const fullRows = format(store.snapshot.meta?.fullRows)
  return [
    { label: '数据总规模', value: fullRows, unit: fullRows === '—' ? undefined : '行', tone: 'warning' },
    { label: '单据平均明细', value: documentLineRatio.value, hint: '行 / 单据', tone: 'accent' },
    { label: '凭证平均分录', value: averageVoucherLines.value, hint: '行 / 凭证', tone: 'success' },
  ]
})

const voucherFacts = computed<MetricItem[]>(() => [
  {
    label: '平均每张凭证',
    value: averageVoucherLines.value,
    unit: '行分录',
    tone: 'accent',
    hint: '借贷平衡规则已启用 · 异常笔数：接口未提供',
  },
])

const integrationHeadline = computed<MetricItem[]>(() => [
  { label: '集成成功率', value: formatPercent(integrationRate.value), tone: 'accent' },
])
const integrationFacts = computed<MetricItem[]>(() => [
  { label: '总调用', value: format(integrationTotal.value) },
  { label: '异常待核', value: format(integrationFailedCount.value), tone: 'danger' },
])

const dualRunHeadline = computed<MetricItem[]>(() => {
  const stats = dualRunStats.value
  if (!stats) return []
  return [
    {
      label: '核对一致率',
      value: formatPercent(stats.consistencyPct),
      tone: dualRunPass.value ? 'success' : 'warning',
      hint: `门禁 ≥ ${dualRunConsistencyRateMin.value}% · ${dualRunPass.value ? '已达标' : '待提升'}`,
    },
  ]
})
const dualRunBreakdownRows = computed<StatRow[]>(() => dualRunBreakdown.value.map((item) => ({
  id: item.type,
  label: item.type.replace('核对', '').replace('比对', ''),
  value: formatPercent(item.rate),
})))

function auditTone(status: QualityAuditItem['status']): BlockTone {
  if (status === 'pass') return 'success'
  if (status === 'unknown') return 'default'
  return 'warning'
}
const qualityAuditItems = computed<MetricItem[]>(() => qualityAuditList.value.map((item) => ({
  label: item.rule,
  value: format(item.total),
  unit: item.unit,
  tone: auditTone(item.status),
  meta: [
    { label: '合规率', value: item.rate != null ? `${item.rate}%` : '—' },
    { label: '异常', value: item.errors != null ? item.errors : '—' },
  ],
})))

const qualityVolumeOption = computed(() => createQualityAuditVolumeOption(qualityAuditList.value))
</script>

<template>
  <div class="flex flex-col gap-2.5 h-full min-h-0 w-full" data-zone="D">
    <!-- D1: 业务规模谱与结构效率，替代四张等权数字卡 -->
    <CockpitPanel
      title="业务运行规模总盘"
      zone="D1"
      :subtitle="`主链路规模与数据结构效率 · 截至 ${store.snapshot.overview.docsAddedAsOfDate || store.snapshot.meta.asOfDate}`"
      class="flex-shrink-0"
    >
      <CommandBand :chart-span="8" :facts="scaleFacts" align="center">
        <template #chart>
          <div class="flex items-center justify-between text-cockpit-xs flex-shrink-0 px-1">
            <span class="font-medium text-slate-300">主链路累计规模谱</span>
            <span class="text-slate-500">单据 / 凭证 / 集成</span>
          </div>
          <VChart class="w-full flex-1 min-h-0" :option="operationsOverviewOption" autoresize />
        </template>
      </CommandBand>
    </CockpitPanel>

    <!-- D2: 全链路流程条 -->
    <CockpitPanel title="业务全链路贯通推进" zone="D2" subtitle="业务单据至凭证集成 6 阶段流水线">
      <div class="flex items-center justify-between gap-2 p-2.5 rounded-xl bg-surface-veil-03 border border-surface-veil-06 overflow-x-auto min-w-0">
        <template v-for="(step, idx) in flowSteps" :key="step.label">
          <div class="flex items-center gap-2.5 min-w-0">
            <div
              class="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0"
              :class="step.status === 'done' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-sky-500/15 text-sky-400'"
            >
              <component :is="step.icon" :size="14" />
            </div>
            <div class="min-w-0">
              <b class="block text-cockpit-sm font-semibold text-slate-200 truncate">{{ step.label }}</b>
              <span class="block font-mono text-cockpit-xs text-slate-400">{{ step.value }}</span>
            </div>
          </div>
          <ArrowRight v-if="idx < flowSteps.length - 1" :size="14" class="text-slate-600 flex-shrink-0" />
        </template>
      </div>
    </CockpitPanel>

    <!-- 主网格：D3-D7 -->
    <div class="grid grid-cols-operations grid-rows-operations gap-2.5 flex-1 min-h-0">
      <!-- D3: 日吞吐与集成质量趋势，不重复 D1/D2 累计规模 -->
      <CockpitPanel title="近 7 日业务吞吐" zone="D3" subtitle="单据、凭证日增与集成成功率">
        <template #actions>
          <PanelLegend compact :items="[
            { label: '单据日增', tone: 'accent' },
            { label: '凭证日增', tone: 'success' },
            { label: '集成成功率', tone: 'warning' },
          ]" />
        </template>
        <VChart v-if="operationsTrend.length" class="w-full h-full min-h-0" :option="operationsTrendOption" autoresize />
        <EmptyNote v-else>暂无连续日吞吐数据</EmptyNote>
      </CockpitPanel>

      <!-- D4: 凭证生成质效 -->
      <CockpitPanel title="凭证生成质效" zone="D4" subtitle="成功率、生成规模与凭证结构">
        <ChartFacts>
          <template #chart><VChart class="w-full h-full min-h-0" :option="voucherQualityOption" autoresize /></template>
          <template #facts><MetricGrid :items="voucherFacts" flat fill /></template>
        </ChartFacts>
      </CockpitPanel>

      <!-- D5: 接口集成入账 (阶梯条充实内容，消除空旷感，D-2) -->
      <CockpitPanel title="接口集成入账" zone="D5" subtitle="实时与批量接口调用结果">
        <ChartFacts variant="facts-led">
          <template #facts>
            <MetricGrid :items="integrationHeadline" flat size="lg" align="center" />
            <MetricGrid :items="integrationFacts" flat size="xs" :columns="2" align="center" />
          </template>
          <template #chart><VChart class="w-full h-full min-h-0" :option="integrationOutcomeOption" autoresize /></template>
        </ChartFacts>
      </CockpitPanel>

      <!-- D6: 双轨运行核对 -->
      <CockpitPanel title="双轨运行核对" zone="D6" subtitle="新老系统一致性对账">
        <ChartFacts v-if="dualRunStats && dualRunOutcomeOption" variant="facts-led">
          <template #facts>
            <MetricGrid :items="dualRunHeadline" flat size="lg" align="center" />
            <!-- 三大对账维度穿透 (KI-053) -->
            <StatList v-if="dualRunBreakdownRows.length" :rows="dualRunBreakdownRows" flat density="dense" class="pt-2 border-t border-surface-veil-06 px-2" />
          </template>
          <template #chart><VChart class="w-full h-full min-h-0" :option="dualRunOutcomeOption" autoresize /></template>
        </ChartFacts>
        <EmptyNote v-else>当前快照未提供双轨明细</EmptyNote>
      </CockpitPanel>

      <!-- D7: 数据质量金标准核验 -->
      <CockpitPanel title="数据质量金标准核验" zone="D7" subtitle="核心业务约束与金标准稽核规则 · 未离线稽核项如实标注，不虚报 0 异常" class="col-span-2">
        <div class="grid grid-cols-12 gap-3 h-full min-h-0">
          <MetricGrid class="col-span-7 pr-3 border-r border-surface-veil-06" :items="qualityAuditItems" :columns="2" fill size="sm" align="center" />

          <!-- 右侧：覆盖规模图表 -->
          <div class="col-span-5 flex flex-1 min-h-0 flex-col pl-1">
            <div class="flex items-center justify-between px-1 text-cockpit-xs flex-shrink-0">
              <div class="flex items-center gap-1.5">
                <span class="w-1.5 h-1.5 rounded-full bg-sky-400" />
                <span class="font-medium text-slate-300">实际核验覆盖规模</span>
              </div>
              <span class="font-mono text-slate-500">对数尺度 · 标签为真实数量</span>
            </div>
            <VChart class="w-full flex-1 min-h-0" :option="qualityVolumeOption" autoresize />
          </div>
        </div>
      </CockpitPanel>
    </div>
  </div>
</template>
