<script setup lang="ts">
import { computed } from 'vue'
import {
  ArrowRight,
  Check,
  FileCheck2,
  Scale,
  ServerCog,
  ShieldCheck,
  Workflow,
} from 'lucide-vue-next'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, GaugeChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import CockpitPanel from '../components/CockpitPanel.vue'
import PanelLegend from '../components/PanelLegend.vue'
import { formatCount, formatPercent } from '../formatters/metrics.ts'
import { useProjectStore } from '../stores/project.ts'
import {
  calcDualRunConsistency,
  buildQualityAuditList,
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

const formatWithUnit = (value: number | null | undefined, unit: string) => {
  const s = format(value)
  return s === '—' ? '—' : `${s} ${unit}`
}

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
  dualRunStats.value ? dualRunStats.value.consistencyPct >= 95 : null
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
      <div class="grid grid-cols-12 gap-3 h-24 min-h-0">
        <section class="col-span-8 flex flex-col min-h-0 pr-3 border-r border-surface-veil-06">
          <div class="flex items-center justify-between text-cockpit-xs flex-shrink-0 px-1">
            <span class="font-medium text-slate-300">主链路累计规模谱</span>
            <span class="text-slate-500">单据 / 凭证 / 集成</span>
          </div>
          <VChart class="w-full flex-1 min-h-0" :option="operationsOverviewOption" autoresize />
        </section>
        <section class="col-span-4 grid grid-cols-3 gap-2 min-h-0">
          <div class="flex flex-col justify-center border-r border-surface-veil-06 pr-2 min-w-0"><span class="text-cockpit-xs text-slate-500">数据总规模</span><b class="font-mono text-cockpit-md text-amber-400 mt-1 truncate">{{ formatWithUnit(store.snapshot.meta?.fullRows, '行') }}</b></div>
          <div class="flex flex-col justify-center border-r border-surface-veil-06 pr-2 min-w-0"><span class="text-cockpit-xs text-slate-500">单据平均明细</span><b class="font-mono text-cockpit-metric text-sky-400 mt-1">{{ documentLineRatio }}</b><span class="text-cockpit-xs text-slate-500">行 / 单据</span></div>
          <div class="flex flex-col justify-center min-w-0"><span class="text-cockpit-xs text-slate-500">凭证平均分录</span><b class="font-mono text-cockpit-metric text-emerald-400 mt-1">{{ averageVoucherLines }}</b><span class="text-cockpit-xs text-slate-500">行 / 凭证</span></div>
        </section>
      </div>
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
        <div v-else class="flex h-full items-center justify-center text-cockpit-xs text-slate-500">暂无连续日吞吐数据</div>
      </CockpitPanel>

      <!-- D4: 凭证生成质效 -->
      <CockpitPanel title="凭证生成质效" zone="D4" subtitle="成功率、生成规模与凭证结构">
        <div class="grid grid-cols-12 gap-3 h-full min-h-0">
          <VChart class="col-span-9 w-full h-full min-h-0" :option="voucherQualityOption" autoresize />
          <div class="col-span-3 flex flex-col justify-center border-l border-surface-veil-06 pl-3 min-w-0">
            <span class="text-cockpit-xs text-slate-500">平均每张凭证</span>
            <div class="flex items-baseline gap-1 mt-1">
              <b class="font-mono text-cockpit-metric text-sky-400">{{ averageVoucherLines }}</b>
              <small class="text-cockpit-xs text-slate-500">行分录</small>
            </div>
            <div class="flex items-center gap-1.5 mt-2 text-cockpit-xs text-emerald-400">
              <ShieldCheck :size="13" class="flex-shrink-0" />
              <span class="truncate">借贷平衡规则已启用</span>
            </div>
            <span class="text-cockpit-xs text-slate-500 mt-1 truncate">异常笔数：接口未提供</span>
          </div>
        </div>
      </CockpitPanel>

      <!-- D5: 接口集成入账 (阶梯条充实内容，消除空旷感，D-2) -->
      <CockpitPanel title="接口集成入账" zone="D5" subtitle="实时与批量接口调用结果">
        <div class="grid grid-cols-12 gap-3 h-full min-h-0">
          <div class="col-span-4 flex flex-col justify-center pr-3 border-r border-surface-veil-06 min-w-0">
            <span class="text-cockpit-xs text-slate-500">集成成功率</span>
            <b class="font-mono text-cockpit-kpi font-bold text-sky-400 mt-1">{{ formatPercent(integrationRate) }}</b>
            <div class="grid grid-cols-2 gap-2 mt-3 text-cockpit-xs">
              <div><span class="block text-slate-500">总调用</span><b class="font-mono text-slate-200">{{ format(integrationTotal) }}</b></div>
              <div><span class="block text-slate-500">异常待核</span><b class="font-mono text-rose-400">{{ format(integrationFailedCount) }}</b></div>
            </div>
          </div>
          <VChart class="col-span-8 w-full h-full min-h-0" :option="integrationOutcomeOption" autoresize />
        </div>
      </CockpitPanel>

      <!-- D6: 双轨运行核对 -->
      <CockpitPanel title="双轨运行核对" zone="D6" subtitle="新老系统一致性对账">
        <div v-if="dualRunStats && dualRunOutcomeOption" class="grid grid-cols-12 gap-3 h-full min-h-0">
          <div class="col-span-4 flex flex-col justify-center pr-3 border-r border-surface-veil-06 min-w-0">
            <span class="text-cockpit-xs text-slate-500">核对一致率</span>
            <b class="font-mono text-cockpit-kpi font-bold mt-1" :class="dualRunPass ? 'text-emerald-400' : 'text-amber-400'">
              {{ formatPercent(dualRunStats.consistencyPct) }}
            </b>
            <div class="flex items-center gap-2 mt-1.5 text-cockpit-xs">
              <span class="text-slate-500">门禁 ≥ 95%</span>
              <span class="font-medium" :class="dualRunPass ? 'text-emerald-400' : 'text-amber-400'">{{ dualRunPass ? '已达标' : '待提升' }}</span>
            </div>
            <!-- 三大对账维度穿透 (KI-053) -->
            <div v-if="dualRunBreakdown.length" class="flex flex-col gap-1 mt-2 pt-2 border-t border-surface-veil-06">
              <div v-for="item in dualRunBreakdown" :key="item.type" class="flex items-center justify-between text-cockpit-xs text-slate-400">
                <span class="truncate max-w-20" :title="item.type">{{ item.type.replace('核对', '').replace('比对', '') }}</span>
                <span class="font-mono font-medium text-slate-200">{{ formatPercent(item.rate) }}</span>
              </div>
            </div>
          </div>
          <VChart class="col-span-8 w-full h-full min-h-0" :option="dualRunOutcomeOption" autoresize />
        </div>
        <div v-else class="flex items-center justify-center h-full text-slate-500 text-cockpit-xs">
          当前快照未提供双轨明细
        </div>
      </CockpitPanel>

      <!-- D7: 数据质量金标准核验 -->
      <CockpitPanel title="数据质量金标准核验" zone="D7" subtitle="核心业务约束与金标准稽核规则 · 未离线稽核项如实标注，不虚报 0 异常" class="col-span-2">
        <div class="grid grid-cols-12 gap-3 h-full min-h-0">
          <!-- 4 项规则 2x2 规整矩阵，科技感指标卡排布 -->
          <div class="col-span-7 grid grid-cols-2 gap-2.5 min-w-0 pr-3 border-r border-surface-veil-06">
            <div
              v-for="item in qualityAuditList"
              :key="item.id"
              class="px-3 py-2 rounded-lg bg-surface-veil-03 border border-surface-veil-06 flex flex-col justify-between min-w-0 transition-colors hover:border-surface-hairline"
              :class="item.status === 'pass'
                ? 'border-l-2 border-l-emerald-500'
                : (item.status === 'unknown'
                  ? 'border-l-2 border-l-slate-600'
                  : 'border-l-2 border-l-amber-500')"
            >
              <!-- 顶部：规则名称与状态胶囊 -->
              <div class="flex items-center justify-between gap-2 min-w-0">
                <div class="flex items-center gap-1.5 min-w-0">
                  <span
                    class="w-1.5 h-1.5 rounded-full flex-shrink-0"
                    :class="item.status === 'pass'
                      ? 'bg-emerald-400'
                      : (item.status === 'unknown' ? 'bg-slate-500' : 'bg-amber-400')"
                  />
                  <span class="text-cockpit-xs text-slate-200 font-medium truncate">{{ item.rule }}</span>
                </div>
                <span
                  class="font-mono text-cockpit-xs px-1.5 py-0.5 rounded border flex-shrink-0"
                  :class="item.status === 'pass'
                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                    : (item.status === 'unknown'
                      ? 'bg-slate-500/10 text-slate-400 border-slate-500/20'
                      : 'bg-amber-500/10 text-amber-400 border-amber-500/20')"
                >
                  {{ item.errors === 0 ? '0 异常' : (item.errors != null ? `${item.errors} 异常` : '—') }}
                </span>
              </div>

              <!-- 中部：核验总规模大字 -->
              <div class="flex items-baseline gap-1 my-0.5 min-w-0">
                <b class="font-mono text-cockpit-metric font-semibold text-slate-100 truncate">{{ format(item.total) }}</b>
                <span class="text-cockpit-xs text-slate-400 flex-shrink-0">{{ item.unit }}</span>
              </div>

              <!-- 底部：合规率及微型进度条 -->
              <div class="flex items-center justify-between gap-2 text-cockpit-xs min-w-0">
                <div class="flex items-center gap-1.5 min-w-0">
                  <span class="text-slate-500 flex-shrink-0">合规率</span>
                  <div class="w-14 h-1 rounded-full bg-surface-veil-06 overflow-hidden flex-shrink-0">
                    <div
                      class="h-full rounded-full transition-all"
                      :class="item.rate != null ? 'bg-emerald-400' : 'bg-slate-600'"
                      :style="{ width: item.rate != null ? `${item.rate}%` : '0%' }"
                    />
                  </div>
                </div>
                <b
                  class="font-mono font-semibold flex-shrink-0"
                  :class="item.rate != null ? 'text-emerald-400' : 'text-slate-500'"
                >
                  {{ item.rate != null ? `${item.rate}%` : '—' }}
                </b>
              </div>
            </div>
          </div>

          <!-- 右侧：覆盖规模图表 -->
          <div class="col-span-5 flex flex-1 min-h-0 flex-col pl-1">
            <div class="flex items-center justify-between px-1 text-cockpit-xs flex-shrink-0">
              <div class="flex items-center gap-1.5">
                <span class="w-1.5 h-1.5 rounded-full bg-sky-400" />
                <span class="font-medium text-slate-300">实际核验覆盖规模</span>
              </div>
              <span class="font-mono text-slate-400 bg-surface-veil-03 px-1.5 py-0.5 rounded border border-surface-veil-06">对数尺度 · 标签为真实数量</span>
            </div>
            <VChart class="w-full flex-1 min-h-0" :option="qualityVolumeOption" autoresize />
          </div>
        </div>
      </CockpitPanel>
    </div>
  </div>
</template>
