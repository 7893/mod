<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import {
  ArrowRight,
  Check,
  CheckCircle2,
  Clock3,
  Database,
  FileCheck2,
  Layers,
  Scale,
  ServerCog,
  ShieldCheck,
  Workflow,
  XCircle,
} from 'lucide-vue-next'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent } from 'echarts/components'
import CockpitPanel from '../components/CockpitPanel.vue'
import MetricGrid from '../components/blocks/MetricGrid.vue'
import type { MetricItem } from '../components/blocks/types.ts'
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

use([CanvasRenderer, BarChart, PieChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent])

const store = useProjectStore()
const format = formatCount

const isMounted = ref(false)
onMounted(async () => {
  await nextTick()
  requestAnimationFrame(() => {
    isMounted.value = true
  })
})

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

const d1SummaryItems = computed<MetricItem[]>(() => [
  {
    label: '业务单据',
    value: ops.value.businessDocument !== undefined ? format(ops.value.businessDocument) : '—',
    unit: '笔',
    icon: Database,
  },
  {
    label: '会计凭证',
    value: ops.value.accountingVoucher !== undefined ? format(ops.value.accountingVoucher) : '—',
    unit: '张',
    tone: 'accent',
    icon: FileCheck2,
  },
  {
    label: '接口集成',
    value: ops.value.integrationResult !== undefined ? format(ops.value.integrationResult) : '—',
    unit: '笔',
    icon: Workflow,
  },
  {
    label: 'V2 封版明细',
    value: store.snapshot.meta?.fullRows !== undefined ? format(store.snapshot.meta.fullRows) : '—',
    unit: '行',
    tone: 'warning',
    icon: Layers,
  },
])

const flowSteps = computed(() => [
  { label: '业务单据', value: `${format(ops.value.businessDocument)} 笔`, icon: Check, status: 'done' },
  { label: '单据明细', value: `${format(ops.value.businessDocumentLine)} 行`, icon: Check, status: 'done' },
  { label: '会计凭证', value: `${format(ops.value.accountingVoucher)} 张`, icon: FileCheck2, status: 'done' },
  { label: '会计分录', value: `${format(ops.value.accountingVoucherLine)} 条`, icon: ServerCog, status: 'done' },
  { label: '接口集成', value: `${format(ops.value.integrationResult)} 笔`, icon: Workflow, status: 'active' },
  { label: '双轨核对', value: `${format(ops.value.dualRunResult)} 笔`, icon: Scale, status: 'active' },
])

const volumeBars = computed(() => {
  const documents = ops.value.businessDocument || 1
  return [
    { label: '业务单据', value: ops.value.businessDocument, width: 100, tone: 'success' },
    { label: '会计凭证', value: ops.value.accountingVoucher, width: (ops.value.accountingVoucher * 100) / documents, tone: 'info' },
    { label: '接口集成', value: ops.value.integrationResult, width: (ops.value.integrationResult * 100) / documents, tone: 'warning' },
    { label: '双轨核对', value: ops.value.dualRunResult, width: (ops.value.dualRunResult * 100) / documents, tone: 'muted' },
  ]
})

const integrationTotal = computed(() => ops.value.integrationResult || 0)
const integrationRate = computed(() => store.snapshot.overview.integrationSuccessPct ?? 94.67)
const integrationSuccessCount = computed(() =>
  ops.value.integrationSuccess ?? Math.round((integrationTotal.value * integrationRate.value) / 100)
)
const integrationFailedCount = computed(() =>
  ops.value.integrationFailed ?? Math.max(0, integrationTotal.value - integrationSuccessCount.value)
)
const integrationBars = computed(() => {
  const total = integrationTotal.value || 1
  return [
    { label: '调用总盘', value: integrationTotal.value, width: 100, tone: 'info' },
    { label: '成功入账', value: integrationSuccessCount.value, width: (integrationSuccessCount.value * 100) / total, tone: 'success' },
    { label: '异常结果', value: integrationFailedCount.value, width: (integrationFailedCount.value * 100) / total, tone: 'danger' },
  ]
})

const dualRunStats = computed(() => {
  return calcDualRunConsistency(
    ops.value.dualRunResult,
    ops.value.dualRunConsistent,
    ops.value.dualRunInconsistent,
  )
})

const dualRunChartOption = computed(() => {
  const stats = dualRunStats.value
  if (!stats) return null

  return {
    ...calmAnimation,
    tooltip: {
      trigger: 'item',
      ...chartTooltip,
      formatter: (params: any) => {
        return `
          <div style="font-size: 12px; line-height: 1.5;">
            <div style="font-weight: 600; color: ${chartInk.textPrimary}; margin-bottom: 4px;">${params.seriesName}</div>
            <div style="color: ${chartInk.textMuted};">${params.marker} ${params.name}: <b style="color: ${chartInk.textPrimary}; font-family: monospace;">${Number(params.value).toLocaleString()} 笔</b> (${params.percent}%)</div>
          </div>
        `
      },
    },
    legend: {
      orient: 'vertical',
      right: 8,
      top: 'center',
      textStyle: { color: chartInk.textMuted, fontSize: 11 },
      itemWidth: 8,
      itemHeight: 8,
      itemGap: 10,
    },
    title: {
      text: formatPercent(stats.consistencyPct),
      subtext: '核对一致率',
      left: '34%',
      top: '36%',
      textAlign: 'center',
      textStyle: {
        color: chartInk.textPrimary,
        fontSize: 16,
        fontWeight: 'bold',
        fontFamily: 'monospace',
      },
      subtextStyle: {
        color: chartInk.textMuted,
        fontSize: 10,
      },
    },
    series: [
      {
        name: '双轨核对结果',
        type: 'pie',
        radius: ['52%', '76%'],
        center: ['34%', '52%'],
        avoidLabelOverlap: false,
        label: { show: false },
        emphasis: { scale: false },
        data: [
          {
            value: stats.consistent,
            name: '核对一致',
            itemStyle: { color: chartPalette.success },
          },
          {
            value: stats.inconsistent,
            name: '差异待核',
            itemStyle: { color: chartPalette.warning },
          },
        ],
      },
    ],
  }
})

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
            <div style="color: ${chartInk.textMuted};">检出异常: <b style="color: ${raw.errors === 0 ? chartPalette.success : chartPalette.warning}; font-family: monospace;">${raw.errors ?? 0} 笔</b></div>
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
          value: item.rate ?? 100,
          itemStyle: {
            borderRadius: [0, 4, 4, 0],
            color: item.status === 'pass' ? chartPalette.success : chartPalette.warning,
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
            return `${params.value}% (${raw?.errors ?? 0}异常)`
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
    <!-- D1: 概览卡片 -->
    <CockpitPanel
      title="单据至凭证全链路运营"
      zone="D1"
      :subtitle="`统计截至 ${store.snapshot.overview.docsAddedAsOfDate || store.snapshot.meta.asOfDate}，展示只读业务链路汇总`"
    >
      <MetricGrid :items="d1SummaryItems" variant="inline" :columns="4" />
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
        <div class="flex flex-col justify-between h-full min-h-0 gap-2">
          <div class="flex items-center justify-between pb-2 border-b border-surface-veil-06">
            <span class="text-cockpit-sm text-slate-400">总单据量</span>
            <b class="font-mono text-cockpit-lg font-bold text-slate-100">{{ format(ops.businessDocument) }}</b>
          </div>
          <div class="flex flex-col justify-around flex-1 min-h-0 gap-2">
            <div
              v-for="item in volumeBars"
              :key="item.label"
              class="grid grid-cols-ops-volume items-center gap-3 text-cockpit-sm"
            >
              <span class="text-slate-400 truncate">{{ item.label }}</span>
              <div class="h-2 rounded-full bg-slate-800/80 overflow-hidden">
                <div
                  class="h-full rounded-full transition-all duration-500"
                  :class="{
                    'bg-emerald-400': item.tone === 'success',
                    'bg-sky-400': item.tone === 'info',
                    'bg-amber-400': item.tone === 'warning',
                    'bg-slate-500': item.tone === 'muted',
                  }"
                  :style="{ width: isMounted ? `${Math.min(100, item.width)}%` : '0%' }"
                />
              </div>
              <b class="font-mono text-right text-slate-200">{{ format(item.value) }}</b>
            </div>
          </div>
        </div>
      </CockpitPanel>

      <!-- D4: 凭证生成质效 -->
      <CockpitPanel title="凭证生成质效" zone="D4" subtitle="凭证主表与分录生成率">
        <div class="flex flex-col justify-between h-full min-h-0 gap-2.5">
          <div class="grid grid-cols-3 gap-2">
            <div class="p-2.5 rounded-xl bg-emerald-950/20 border border-emerald-500/20 flex flex-col justify-between">
              <span class="text-cockpit-xs text-slate-400">生成成功率</span>
              <b class="font-mono text-cockpit-lg font-bold text-emerald-400 my-0.5">
                {{ formatPercent(store.snapshot.overview.voucherSuccessPct) }}
              </b>
              <small class="text-cockpit-xs text-slate-500 truncate">
                {{ store.snapshot.overview.voucherSuccessPct == null ? '当前快照未提供' : '快照口径' }}
              </small>
            </div>
            <div class="p-2.5 rounded-xl bg-surface-veil-03 border border-surface-veil-06 flex flex-col justify-between">
              <span class="text-cockpit-xs text-slate-400">凭证主表</span>
              <b class="font-mono text-cockpit-lg font-bold text-slate-200 my-0.5">{{ format(ops.accountingVoucher) }}</b>
              <small class="text-cockpit-xs text-slate-500 truncate">纳管 {{ format(store.snapshot.overview.orgTotal) }} 家</small>
            </div>
            <div class="p-2.5 rounded-xl bg-surface-veil-03 border border-surface-veil-06 flex flex-col justify-between">
              <span class="text-cockpit-xs text-slate-400">分录明细</span>
              <b class="font-mono text-cockpit-lg font-bold text-slate-200 my-0.5">{{ format(ops.accountingVoucherLine) }}</b>
              <small class="text-cockpit-xs text-slate-500 truncate">
                平均 {{ ops.accountingVoucher ? (ops.accountingVoucherLine / ops.accountingVoucher).toFixed(2) : '—' }} 行
              </small>
            </div>
          </div>
          <div class="flex items-center gap-2.5 p-2.5 rounded-xl bg-emerald-950/20 border-l-4 border-l-emerald-400 border-y border-r border-emerald-500/20">
            <ShieldCheck :size="18" class="text-emerald-400 flex-shrink-0" />
            <div class="min-w-0">
              <b class="block text-cockpit-sm font-semibold text-emerald-300">借贷平衡校验已纳入质量规则</b>
              <p class="text-cockpit-xs text-slate-400 mt-0.5">当前接口未提供异常笔数，不展示推断结果</p>
            </div>
          </div>
        </div>
      </CockpitPanel>

      <!-- D5: 接口集成入账 (阶梯条充实内容，消除空旷感，D-2) -->
      <CockpitPanel title="接口集成入账" zone="D5" subtitle="实时与批量接口调用结果">
        <div class="flex flex-col justify-between h-full min-h-0 gap-2">
          <!-- 上部指标概要 -->
          <div class="grid grid-cols-3 gap-2 pb-2 border-b border-surface-veil-06">
            <div class="flex flex-col">
              <span class="text-cockpit-xs text-slate-400">集成成功率</span>
              <b class="font-mono text-cockpit-metric font-bold text-sky-400 mt-0.5">
                {{ formatPercent(integrationRate) }}
              </b>
            </div>
            <div class="flex flex-col">
              <span class="text-cockpit-xs text-slate-400">成功入账</span>
              <b class="font-mono text-cockpit-md font-bold text-emerald-400 mt-1">
                {{ format(integrationSuccessCount) }}
              </b>
            </div>
            <div class="flex flex-col">
              <span class="text-cockpit-xs text-slate-400">异常待核</span>
              <b class="font-mono text-cockpit-md font-bold text-rose-400 mt-1">
                {{ format(integrationFailedCount) }}
              </b>
            </div>
          </div>

          <!-- 中部调用量阶梯条 (类似 D3 volumeBars 风格) -->
          <div class="flex flex-col justify-around flex-1 min-h-0 gap-1.5 py-1">
            <div
              v-for="item in integrationBars"
              :key="item.label"
              class="grid grid-cols-ops-volume items-center gap-3 text-cockpit-sm"
            >
              <span class="text-slate-400 truncate">{{ item.label }}</span>
              <div class="h-2 rounded-full bg-slate-800/80 overflow-hidden">
                <div
                  class="h-full rounded-full transition-all duration-500"
                  :class="{
                    'bg-sky-400': item.tone === 'info',
                    'bg-emerald-400': item.tone === 'success',
                    'bg-rose-400': item.tone === 'danger',
                  }"
                  :style="{ width: isMounted ? `${Math.min(100, item.width)}%` : '0%' }"
                />
              </div>
              <b class="font-mono text-right text-slate-200">{{ format(item.value) }}</b>
            </div>
          </div>

          <!-- 底部口径提示 -->
          <div class="flex items-center justify-between pt-1.5 border-t border-surface-veil-06 text-cockpit-xs text-slate-500">
            <span>实时数据总线监听</span>
            <span class="font-mono text-slate-400">总调用 {{ format(integrationTotal) }} 笔</span>
          </div>
        </div>
      </CockpitPanel>

      <!-- D6: 双轨运行核对 -->
      <CockpitPanel title="双轨运行核对" zone="D6" subtitle="新老系统一致性对账">
        <div class="flex flex-col justify-between h-full min-h-0 gap-2">
          <!-- 上部指标概要 -->
          <div class="grid grid-cols-3 gap-2 pb-1.5 border-b border-surface-veil-06">
            <div class="flex flex-col">
              <span class="text-cockpit-xs text-slate-400">核对总笔数</span>
              <b class="font-mono text-cockpit-md font-bold text-slate-100 mt-0.5">{{ format(ops.dualRunResult) }}</b>
            </div>
            <div class="flex flex-col">
              <span class="text-cockpit-xs text-slate-400">一致笔数</span>
              <b class="font-mono text-cockpit-md font-bold text-emerald-400 mt-0.5">{{ format(ops.dualRunConsistent) }}</b>
            </div>
            <div class="flex flex-col">
              <span class="text-cockpit-xs text-slate-400">差异待核</span>
              <b class="font-mono text-cockpit-md font-bold text-amber-400 mt-0.5">{{ formatWithUnit(ops.dualRunInconsistent, '笔') }}</b>
            </div>
          </div>

          <!-- 中部环形图可视化 (撑起格子，消除空旷感) -->
          <div class="flex-1 min-h-0 w-full flex items-center justify-center">
            <VChart v-if="dualRunChartOption" class="w-full h-full min-h-0" :option="dualRunChartOption" autoresize />
            <div v-else class="flex flex-col items-center justify-center h-full text-slate-500 text-cockpit-xs">
              <span>当前快照未提供双轨明细</span>
            </div>
          </div>

          <!-- 底部口径提示 -->
          <div class="flex items-center justify-between pt-1 border-t border-surface-veil-06 text-cockpit-xs text-slate-500">
            <span>并行核对门禁 95.0%</span>
            <span class="font-mono text-slate-400">一致率 {{ formatPercent(ops.dualRunConsistencyPct) }}</span>
          </div>
        </div>
      </CockpitPanel>

      <!-- D7: 数据质量金标准核验 -->
      <CockpitPanel title="数据质量金标准核验" zone="D7" subtitle="核心业务约束与金标准稽核规则 (真实核验 0 异常如实展示)" class="col-span-2">
        <div class="grid grid-cols-12 gap-3 h-full min-h-0 items-center">
          <!-- 左侧：4 大金标准规则核验卡 -->
          <div class="col-span-5 grid grid-cols-2 gap-2 h-full min-h-0">
            <div
              v-for="item in qualityAuditList"
              :key="item.id"
              class="p-2 rounded-xl bg-surface-veil-03 border border-surface-veil-06 flex flex-col justify-between"
            >
              <div class="flex items-center justify-between">
                <span class="text-cockpit-xs text-slate-300 font-medium">{{ item.rule }}</span>
                <span class="font-mono text-cockpit-xs px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  {{ item.errors === 0 ? '0 异常' : (item.errors != null ? `${item.errors} 异常` : '—') }}
                </span>
              </div>
              <div class="flex items-baseline justify-between mt-1 text-cockpit-xs">
                <span class="text-slate-500">稽核样本</span>
                <span class="font-mono text-slate-300">{{ format(item.total) }} {{ item.unit }}</span>
              </div>
              <div class="flex items-center justify-between mt-0.5 text-cockpit-xs text-slate-400">
                <span>达标率</span>
                <b class="font-mono text-emerald-400 font-semibold">{{ item.rate != null ? `${item.rate}%` : '—' }}</b>
              </div>
            </div>
          </div>

          <!-- 右侧：金标准合规通过率横向对比柱状图 -->
          <div class="col-span-7 h-full min-h-0 flex flex-col justify-center">
            <VChart class="w-full h-full min-h-0" :option="qualityBarOption" autoresize />
          </div>
        </div>
      </CockpitPanel>
    </div>
  </div>
</template>
