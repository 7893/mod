<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import {
  Building,
  Layers,
  UserCheck,
  Users,
} from 'lucide-vue-next'
import CockpitPanel from '../components/CockpitPanel.vue'
import MetricGrid from '../components/blocks/MetricGrid.vue'
import ChartBlock from '../components/blocks/ChartBlock.vue'
import RolloutLedgerTable from '../components/RolloutLedgerTable.vue'
import type { MetricItem } from '../components/blocks/types.ts'
import { chartInk, chartPalette } from '../charts/theme.ts'
import { useProjectStore } from '../stores/project.ts'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent])

const store = useProjectStore()

const format = (value: number | undefined) => (
  value === undefined ? '—' : new Intl.NumberFormat('zh-CN').format(value)
)

const batches = computed(() => store.snapshot.rollout || [])

const c1SummaryItems = computed<MetricItem[]>(() => [
  {
    label: '已上线',
    value: store.snapshot.overview.launched ? format(store.snapshot.overview.launched) : '—',
    unit: '家',
    tone: 'success',
    hint: `占总纳管 ${store.snapshot.overview.launchedPct || 37.4}%`,
  },
  {
    label: '双轨运行',
    value: store.snapshot.overview.dual ? format(store.snapshot.overview.dual) : '—',
    unit: '家',
    tone: 'warning',
    hint: '双轨核对平账阶段',
  },
  {
    label: '准备/建设',
    value: (
      store.snapshot.overview.orgTotal !== undefined &&
      store.snapshot.overview.launched !== undefined &&
      store.snapshot.overview.dual !== undefined
    )
      ? format(store.snapshot.overview.orgTotal - store.snapshot.overview.launched - store.snapshot.overview.dual)
      : '—',
    unit: '家',
    hint: '在建联调与储备批次',
  },
])

const contactItems = computed<MetricItem[]>(() => [
  {
    label: '联系人总数',
    value: (store.snapshot.overview.contactsTotal || 15613).toLocaleString(),
    icon: Users,
    tone: 'accent',
  },
  {
    label: '单位覆盖率',
    value: String(store.snapshot.overview.contactsCoveragePct || 100),
    unit: '%',
    icon: UserCheck,
    tone: 'success',
  },
  {
    label: '已覆盖单位',
    value: (store.snapshot.overview.contactsCoveredOrgs || 2000).toLocaleString(),
    unit: '家',
    icon: Building,
  },
  {
    label: '纳管总数',
    value: (store.snapshot.overview.orgTotal || 2000).toLocaleString(),
    unit: '家',
    icon: Layers,
  },
])

// 色值统一取自 charts/theme.ts，避免图表区与页面外壳出现两套蓝绿黄
const chartColors = {
  accent: chartPalette.accent,
  warning: chartPalette.warning,
  success: chartPalette.success,
  bg: chartInk.bgTooltip,
  border: chartInk.border,
  textMuted: chartInk.textMuted,
}

const batchChartOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    backgroundColor: chartColors.bg,
    borderColor: chartColors.border,
    textStyle: { color: chartInk.textPrimary, fontSize: 12 },
  },
  grid: { left: 12, right: 12, top: 24, bottom: 24, containLabel: true },
  xAxis: {
    type: 'category',
    data: batches.value.map((v) => v.name),
    axisLine: { lineStyle: { color: chartColors.border } },
    axisLabel: { color: chartColors.textMuted, fontSize: 11 },
  },
  yAxis: {
    type: 'value',
    max: 100,
    splitLine: { lineStyle: { color: chartColors.border, opacity: 0.4 } },
    axisLabel: { color: chartColors.textMuted, fontSize: 11, formatter: '{value}%' },
  },
  series: [
    {
      name: '上线率',
      type: 'bar',
      data: batches.value.map((v) => v.launchedPct),
      barWidth: '34%', barMaxWidth: 34,
      itemStyle: { color: chartColors.accent, borderRadius: [3, 3, 0, 0] },
    },
    {
      name: '建设完成度',
      type: 'line',
      data: batches.value.map((v) => v.constructionPct),
      symbolSize: 5,
      lineStyle: { color: chartColors.warning, width: 2 },
      itemStyle: { color: chartColors.warning },
    },
  ],
}))

const provinceRolloutRanking = computed(() => {
  const list = [...store.provinceSummary]
  return list
    .map((p) => ({
      ...p,
      launchedPct: p.total > 0 ? Math.round((p.launched * 100) / p.total) : 0,
      unlaunched: Math.max(0, p.total - p.launched - p.dual),
    }))
    .sort((a, b) => b.launched - a.launched || b.total - a.total)
})

const topProvinces = computed(() => provinceRolloutRanking.value.slice(0, 6))

const c4Stats = computed<MetricItem[]>(() => [
  { label: '覆盖省份', value: 34 },
  { label: '最高上线', value: topProvinces.value[0]?.name || '—' },
  { label: '平均上线率', value: String(store.snapshot.overview.launchedPct || 37.4), unit: '%' },
])

const provinceRolloutOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    backgroundColor: chartColors.bg,
    borderColor: chartColors.border,
    textStyle: { color: chartInk.textPrimary, fontSize: 12 },
  },
  legend: {
    data: ['已上线', '双轨', '其他'],
    top: 0,
    right: 4,
    textStyle: { color: chartColors.textMuted, fontSize: 10 },
    itemWidth: 10,
    itemHeight: 8,
  },
  grid: { left: 4, right: 10, top: 26, bottom: 4, containLabel: true },
  xAxis: {
    type: 'value',
    splitLine: { lineStyle: { color: chartColors.border, opacity: 0.4 } },
    axisLabel: { color: chartColors.textMuted, fontSize: 10 },
  },
  yAxis: {
    type: 'category',
    data: topProvinces.value.map((v) => v.name).reverse(),
    axisLine: { lineStyle: { color: chartColors.border } },
    // interval: 0 强制每个省份都出标签。默认策略在容器变矮时会隔项跳过，
    // 结果画了 6 条却只标出 3 个省名，读者无法把条形对应到省份。
    axisLabel: { color: chartColors.textMuted, fontSize: 11, interval: 0 },
  },
  series: [
    {
      name: '已上线',
      type: 'bar',
      stack: 'total',
      barMaxWidth: 14,
      data: topProvinces.value.map((v) => v.launched).reverse(),
      itemStyle: { color: chartColors.accent },
    },
    {
      name: '双轨',
      type: 'bar',
      stack: 'total',
      data: topProvinces.value.map((v) => v.dual).reverse(),
      itemStyle: { color: chartColors.warning },
    },
    {
      name: '其他',
      type: 'bar',
      stack: 'total',
      data: topProvinces.value.map((v) => v.unlaunched).reverse(),
      itemStyle: { color: chartColors.border },
    },
  ],
}))
</script>

<template>
  <div class="w-full h-full p-3 bg-surface-base flex flex-col gap-2.5 overflow-hidden" data-zone="C">
    <!-- C1: 概览指标 -->
    <CockpitPanel
      title="推广上线与批次台账"
      zone="C1"
      :subtitle="`${batches.length} 个批次 · ${format(store.snapshot.overview.orgTotal)} 家单位 · 已上线 ${format(store.snapshot.overview.launched)} 家 (${store.snapshot.overview.launchedPct || 37.4}%)`"
      class="flex-shrink-0"
    >
      <MetricGrid :items="c1SummaryItems" variant="inline" :columns="3" />
    </CockpitPanel>

    <!-- C2: 8 批次工序卡片流水线 (横向滚动容器，8批始终呈现，窗口缩小时可横滑，C-1) -->
    <CockpitPanel
      title="批次推进工序梯队"
      zone="C2"
      subtitle="8 批次全生命周期流水线"
      class="flex-shrink-0"
    >
      <div class="flex gap-2.5 overflow-x-auto h-full">
        <div
          v-for="b in batches"
          :key="b.batchId"
          class="flex-1 min-w-[110px] flex flex-col justify-between p-2.5 rounded-xl bg-surface-veil-03 border border-surface-veil-06 min-h-0 flex-shrink-0"
        >
          <div class="flex items-center justify-between gap-1 mb-1">
            <b class="text-cockpit-md font-semibold text-slate-100 truncate">{{ b.name }}</b>
            <span
              class="text-cockpit-xs font-medium px-1.5 py-0.5 rounded border whitespace-nowrap"
              :class="b.batchId === 8
                ? 'bg-slate-800/60 text-slate-400 border-white/10'
                : (b.launchedPct === 100
                  ? 'bg-emerald-950/40 text-emerald-400 border-emerald-500/30'
                  : (b.dual > 0
                    ? 'bg-amber-950/40 text-amber-400 border-amber-500/30'
                    : 'bg-sky-950/40 text-sky-400 border-sky-500/30'))"
            >
              {{ b.batchId === 8 ? '待启动储备' : (b.stageLabel || (b.launchedPct === 100 ? '已投产运行' : b.dual > 0 ? '双轨比对' : '联调在建')) }}
            </span>
          </div>
          <div class="grid grid-cols-3 gap-1 text-cockpit-xs text-slate-400 my-1.5">
            <div>纳管 <b class="font-mono text-slate-200 block text-cockpit-sm">{{ b.total }}</b></div>
            <div>上线 <b class="font-mono text-emerald-400 block text-cockpit-sm">{{ b.launched }}</b></div>
            <div>双轨 <b class="font-mono text-sky-400 block text-cockpit-sm">{{ b.dual }}</b></div>
          </div>
          <div class="flex items-center gap-2 mt-auto">
            <div class="flex-1 h-1.5 rounded-full bg-slate-800/80 overflow-hidden">
              <div
                class="h-full rounded-full transition-all duration-500"
                :class="b.launchedPct === 100 ? 'bg-emerald-400' : 'bg-sky-400'"
                :style="{ width: `${b.launchedPct}%` }"
              />
            </div>
            <span class="font-mono text-cockpit-xs font-semibold text-slate-300 w-8 text-right">
              {{ b.launchedPct }}%
            </span>
          </div>
        </div>
      </div>
    </CockpitPanel>

    <!-- 中部三栏：C3 上线趋势 + C4 省域上线分布 + C5 项目联系人 (弹性优先，Guardrail 扩大为 min-h-[200px] max-h-[320px]，C-2) -->
    <div class="grid grid-cols-rollout-mid gap-2.5 min-h-[200px] max-h-[320px] flex-1">
      <CockpitPanel title="上线趋势" zone="C3" subtitle="批次演进与完成度">
        <VChart class="w-full h-full min-h-0" :option="batchChartOption" autoresize />
      </CockpitPanel>

      <CockpitPanel title="省域上线分布" zone="C4" subtitle="34 省上线率排行">
        <ChartBlock :stats="c4Stats">
          <VChart class="w-full h-full min-h-0" :option="provinceRolloutOption" autoresize />
        </ChartBlock>
      </CockpitPanel>

      <CockpitPanel title="项目联系人" zone="C5" subtitle="组织覆盖与专员">
        <div class="flex flex-col justify-between h-full min-h-0 gap-2">
          <MetricGrid :items="contactItems" variant="inline" :columns="2" fill />
          <p class="text-center text-cockpit-xs text-slate-500 tracking-wide">* 均为规则推导的项目联系人</p>
        </div>
      </CockpitPanel>
    </div>

    <!-- C6: 单位台账表格与分页组件 -->
    <RolloutLedgerTable class="flex-1 min-h-0" />
  </div>
</template>
