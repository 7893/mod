<script setup lang="ts">
import { computed } from 'vue'
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
import CockpitPanel from '../components/CockpitPanel.vue'
import MetricGrid from '../components/blocks/MetricGrid.vue'
import type { MetricItem } from '../components/blocks/types.ts'
import { formatCount, formatPercent } from '../formatters/metrics.ts'
import { useProjectStore } from '../stores/project.ts'

const store = useProjectStore()
const format = formatCount

const formatWithUnit = (value: number | null | undefined, unit: string) => {
  const s = format(value)
  return s === '—' ? '—' : `${s} ${unit}`
}

const qualityItems: MetricItem[] = [
  { label: '借贷平衡', value: '已纳入', unit: '校验规则', icon: ShieldCheck, tone: 'success', hint: '借贷平衡规则纳入封版质量校验' },
  { label: '时间顺序', value: '已纳入', unit: '校验规则', icon: ShieldCheck, tone: 'success', hint: '核验单据提交、审批、制证时间戳顺序' },
  { label: '孤儿链路', value: '已纳入', unit: '校验规则', icon: ShieldCheck, tone: 'success', hint: '单据凭证关系纳入孤儿链路校验' },
  { label: '状态演进', value: '已纳入', unit: '快照追踪', icon: ShieldCheck, tone: 'success', hint: '按单位历史快照追踪全周期状态变化' },
]

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
                  :style="{ width: `${Math.min(100, item.width)}%` }"
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

      <!-- D5: 接口集成入账 -->
      <CockpitPanel title="接口集成入账" zone="D5" subtitle="实时与批量接口调用结果">
        <div class="flex items-center justify-around h-full min-h-0 gap-4 px-2">
          <div class="flex flex-col items-center justify-center text-center">
            <span class="text-cockpit-sm text-slate-400 mb-1">集成成功率</span>
            <b class="font-mono text-cockpit-metric font-bold text-sky-400">
              {{ formatPercent(store.snapshot.overview.integrationSuccessPct) }}
            </b>
          </div>
          <div class="h-14 w-px bg-surface-veil-06"></div>
          <div class="flex flex-col justify-center gap-2 min-w-44">
            <div class="flex items-center justify-between gap-3 text-cockpit-sm">
              <div class="flex items-center gap-2 text-slate-300">
                <CheckCircle2 :size="15" class="text-emerald-400 flex-shrink-0" />
                <span>成功入账</span>
              </div>
              <b class="font-mono text-slate-100">{{ formatWithUnit(ops.integrationSuccess, '笔') }}</b>
            </div>
            <div class="flex items-center justify-between gap-3 text-cockpit-sm">
              <div class="flex items-center gap-2 text-slate-300">
                <XCircle :size="15" class="text-rose-400 flex-shrink-0" />
                <span>异常结果</span>
              </div>
              <b class="font-mono text-rose-400">{{ formatWithUnit(ops.integrationFailed, '笔') }}</b>
            </div>
            <div class="flex items-center justify-between gap-3 text-cockpit-sm">
              <div class="flex items-center gap-2 text-slate-300">
                <Clock3 :size="15" class="text-sky-400 flex-shrink-0" />
                <span>数据口径</span>
              </div>
              <b class="font-mono text-slate-300">当前快照</b>
            </div>
          </div>
        </div>
      </CockpitPanel>

      <!-- D6: 双轨运行核对 -->
      <CockpitPanel title="双轨运行核对" zone="D6" subtitle="新老系统一致性对账">
        <div class="flex flex-col justify-between h-full min-h-0 gap-2.5">
          <div class="grid grid-cols-3 gap-2 p-2.5 rounded-xl bg-surface-veil-03 border border-surface-veil-06">
            <div class="flex flex-col">
              <span class="text-cockpit-xs text-slate-400">核对总笔数</span>
              <b class="font-mono text-cockpit-lg font-bold text-slate-100 mt-1">{{ format(ops.dualRunResult) }}</b>
            </div>
            <div class="flex flex-col">
              <span class="text-cockpit-xs text-slate-400">一致笔数</span>
              <b class="font-mono text-cockpit-lg font-bold text-emerald-400 mt-1">{{ format(ops.dualRunConsistent) }}</b>
            </div>
            <div class="flex flex-col">
              <span class="text-cockpit-xs text-slate-400">不一致</span>
              <b class="font-mono text-cockpit-lg font-bold text-amber-400 mt-1">{{ formatWithUnit(ops.dualRunInconsistent, '笔') }}</b>
            </div>
          </div>
          <p class="text-cockpit-xs text-slate-400 px-1">
            核对一致率 <span class="font-mono font-semibold text-slate-200">{{ formatPercent(ops.dualRunConsistencyPct) }}</span>，仅展示当前数据库汇总结果
          </p>
        </div>
      </CockpitPanel>

      <!-- D7: 数据质量金标准核验 -->
      <CockpitPanel title="数据质量金标准核验" zone="D7" subtitle="核心业务约束与稽核规则" class="col-span-2">
        <MetricGrid :items="qualityItems" :columns="4" size="sm" fill />
      </CockpitPanel>
    </div>
  </div>
</template>
