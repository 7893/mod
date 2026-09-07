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
import { BarChart, GaugeChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import CockpitPanel from '../components/CockpitPanel.vue'
import { formatCount, formatPercent } from '../formatters/metrics.ts'
import { useProjectStore } from '../stores/project.ts'
import {
  chartPalette,
  chartInk,
  chartTooltip,
  valueAxis,
  calmAnimation,
} from '../charts/theme.ts'
import {
  calcDualRunConsistency,
  buildQualityAuditList,
} from '../utils/qualityMetrics.ts'
import {
  createDualRunOutcomeOption,
  createIntegrationOutcomeOption,
  createOperationsFlowOption,
  createOperationsOverviewOption,
  createVoucherQualityOption,
} from '../charts/operationsOptions.ts'

use([CanvasRenderer, BarChart, GaugeChart, GridComponent, TooltipComponent])

const store = useProjectStore()
const format = formatCount

const formatWithUnit = (value: number | null | undefined, unit: string) => {
  const s = format(value)
  return s === '—' ? '—' : `${s} ${unit}`
}

const ops = computed(() => store.snapshot.operations || {
  businessDocument: 5050416,
  businessDocumentLine: 10066501,
  accountingVoucher: 3223900,
  accountingVoucherLine: 6418622,
  documentVoucherLink: 3201490,
  integrationResult: 3031157,
  dualRunResult: 29810,
})

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
const operationsFlowOption = computed(() => createOperationsFlowOption(ops.value))
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

const qualityAuditList = computed(() => {
  return buildQualityAuditList(
    store.snapshot.quality,
    ops.value,
    store.snapshot.overview.orgTotal,
  )
})

const qualityBarOption = computed(() => {
  const list = [...qualityAuditList.value].reverse()
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
        return `
          <div style="font-size: 12px; line-height: 1.6;">
            <div style="font-weight: 600; color: ${chartInk.textPrimary}; margin-bottom: 4px;">${raw.rule}</div>
            <div style="color: ${chartInk.textMuted};">稽核规模: <b style="color: ${chartInk.textPrimary}; font-family: monospace;">${format(raw.total)} ${raw.unit}</b></div>
            <div style="color: ${chartInk.textMuted};">检出异常: <b style="color: ${raw.errors === 0 ? chartPalette.success : chartPalette.warning}; font-family: monospace;">${raw.errors != null ? `${raw.errors} 笔` : '—'}</b></div>
            <div style="color: ${chartInk.textMuted};">合规达成率: <b style="color: ${chartPalette.success}; font-family: monospace;">${raw.rate != null ? `${raw.rate}%` : '—'}</b></div>
            <div style="color: ${chartInk.textMuted}; margin-top: 4px; border-top: 1px dashed ${chartInk.borderSoft}; padding-top: 4px;">${raw.hint}</div>
          </div>
        `
      },
    },
    grid: {
      top: 10,
      bottom: 20,
      left: 80,
      right: 120,
      containLabel: true,
    },
    xAxis: {
      ...valueAxis,
      max: 100,
      splitNumber: 4,
      axisLabel: {
        color: chartInk.textMuted,
        fontSize: 10,
        fontFamily: 'monospace',
        formatter: '{value}%',
      },
      splitLine: {
        lineStyle: {
          color: chartInk.borderSoft,
          type: 'dashed',
        },
      },
    },
    yAxis: {
      type: 'category',
      data: list.map((i) => i.rule),
      axisLabel: {
        color: chartInk.textMuted,
        fontSize: 11,
      },
      axisTick: { show: false },
      axisLine: {
        lineStyle: { color: chartInk.border },
      },
    },
    series: [
      {
        name: '合规率',
        type: 'bar',
        barWidth: 12,
        data: list.map((item) => ({
          value: item.rate,
          itemStyle: {
            borderRadius: [0, 4, 4, 0],
            color: item.status === 'pass'
              ? chartPalette.success
              : (item.status === 'unknown' ? chartPalette.neutral : chartPalette.warning),
          },
        })),
        label: {
          show: true,
          position: 'right',
          color: chartPalette.success,
          fontFamily: 'monospace',
          fontSize: 11,
          fontWeight: 'bold',
          formatter: (params: any) => {
            const raw = list[params.dataIndex]
            if (!raw || raw.rate == null) return '—'
            return `${raw.rate}% (${raw.errors ?? '—'}异常)`
          },
        },
        showBackground: true,
        backgroundStyle: {
          color: 'rgba(255, 255, 255, 0.03)',
          borderRadius: [0, 4, 4, 0],
        },
      },
    ],
  }
})
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
      <!-- D3: 链路规模对比 -->
      <CockpitPanel title="链路规模对比" zone="D3" subtitle="单据与下游凭证/集成数据量阶梯">
        <VChart class="w-full h-full min-h-0" :option="operationsFlowOption" autoresize />
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
            <div class="flex items-center gap-2 mt-3 text-cockpit-xs">
              <span class="text-slate-500">门禁 ≥ 95%</span>
              <span class="font-medium" :class="dualRunPass ? 'text-emerald-400' : 'text-amber-400'">{{ dualRunPass ? '已达标' : '待提升' }}</span>
            </div>
          </div>
          <VChart class="col-span-8 w-full h-full min-h-0" :option="dualRunOutcomeOption" autoresize />
        </div>
        <div v-else class="flex items-center justify-center h-full text-slate-500 text-cockpit-xs">
          当前快照未提供双轨明细
        </div>
      </CockpitPanel>

      <!-- D7: 数据质量金标准核验 -->
      <CockpitPanel title="数据质量金标准核验" zone="D7" subtitle="核心业务约束与金标准稽核规则 (真实核验 0 异常如实展示)" class="col-span-2">
        <div class="flex flex-col gap-2 h-full min-h-0">
          <!-- 四项规则压缩成单行状态带，把主要面积交给趋势比较 -->
          <div class="grid grid-cols-4 gap-2 flex-shrink-0">
            <div
              v-for="item in qualityAuditList"
              :key="item.id"
              class="px-2.5 py-2 rounded-lg bg-surface-veil-03 border border-surface-veil-06 min-w-0"
            >
              <div class="flex items-center justify-between gap-2">
                <span class="text-cockpit-xs text-slate-300 font-medium truncate">{{ item.rule }}</span>
                <span class="font-mono text-cockpit-xs px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  {{ item.errors === 0 ? '0 异常' : (item.errors != null ? `${item.errors} 异常` : '—') }}
                </span>
              </div>
              <div class="flex items-center justify-between mt-1 text-cockpit-xs">
                <span class="font-mono text-slate-500">{{ format(item.total) }} {{ item.unit }}</span>
                <b class="font-mono text-emerald-400">{{ item.rate != null ? `${item.rate}%` : '—' }}</b>
              </div>
            </div>
          </div>

          <div class="flex-1 min-h-0">
            <VChart class="w-full h-full min-h-0" :option="qualityBarOption" autoresize />
          </div>
        </div>
      </CockpitPanel>
    </div>
  </div>
</template>
