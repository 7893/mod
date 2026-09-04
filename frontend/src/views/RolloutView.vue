<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import {
  Building,
  Layers,
  Search,
  UserCheck,
  Users,
  X,
} from 'lucide-vue-next'
import CockpitPanel from '../components/CockpitPanel.vue'
import MetricGrid from '../components/blocks/MetricGrid.vue'
import ChartBlock from '../components/blocks/ChartBlock.vue'
import type { MetricItem } from '../components/blocks/types.ts'
import { chartInk, chartPalette } from '../charts/theme.ts'
import { formatPercent } from '../formatters/metrics.ts'
import { useProjectStore, type EntityRow, type RolloutStatus } from '../stores/project.ts'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent])

const store = useProjectStore()
const query = ref('')
const selectedBatch = ref('全部')
const selectedProvince = ref('全部')
const editing = ref<EntityRow | null>(null)
const draft = ref<Partial<EntityRow>>({})
const page = ref(1)
const pageSize = ref(20)

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
const NATIONAL_PROVINCE_ORDER = [
  '北京', '天津', '河北', '山西', '内蒙古',
  '辽宁', '吉林', '黑龙江',
  '上海', '江苏', '浙江', '安徽', '福建', '江西', '山东',
  '河南', '湖北', '湖南', '广东', '广西', '海南',
  '重庆', '四川', '贵州', '云南', '西藏',
  '陕西', '甘肃', '青海', '宁夏', '新疆',
  '香港', '澳门', '台湾',
]

const provinces = computed(() => {
  const existing = new Set(store.entities.map((row) => row.province))
  const ordered = NATIONAL_PROVINCE_ORDER.filter((p) => existing.has(p))
  const remaining = [...existing].filter((p) => !NATIONAL_PROVINCE_ORDER.includes(p))
  return ['全部', ...ordered, ...remaining]
})

const BATCH_ORDER = ['第一批', '第二批', '第三批', '第四批', '第五批', '第六批', '第七批', '第八批']
const batchOptions = computed(() => {
  const existing = new Set(store.entities.map((row) => row.batch))
  const ordered = BATCH_ORDER.filter((b) => existing.has(b))
  return ['全部', ...ordered]
})

const filteredEntities = computed(() => {
  return store.entities.filter((row) => {
    const matchBatch = selectedBatch.value === '全部' || row.batch === selectedBatch.value
    const matchProv = selectedProvince.value === '全部' || row.province === selectedProvince.value
    const matchQuery = !query.value || `${row.name}${row.owner}${row.province}${row.batch}`.includes(query.value)
    return matchBatch && matchProv && matchQuery
  })
})

const paginatedEntities = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredEntities.value.slice(start, start + pageSize.value)
})

const totalPages = computed(() => Math.ceil(filteredEntities.value.length / pageSize.value) || 1)

function openEdit(row: EntityRow) {
  editing.value = row
  draft.value = { ...row }
}

function save() {
  if (!editing.value) return
  store.updateEntity(editing.value.id, {
    status: draft.value.status as RolloutStatus,
    construction: Number(draft.value.construction),
    openingData: Number(draft.value.openingData),
    owner: String(draft.value.owner),
  })
  editing.value = null
}

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

    <!-- C2: 8 批次工序卡片流水线 -->
    <CockpitPanel
      title="批次推进工序梯队"
      zone="C2"
      subtitle="8 批次全生命周期流水线"
      class="flex-shrink-0"
    >
      <div class="grid grid-cols-8 gap-2.5 h-full">
        <div
          v-for="b in batches"
          :key="b.batchId"
          class="flex flex-col justify-between p-2.5 rounded-xl bg-surface-veil-03 border border-surface-veil-06 min-h-0"
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

    <!-- 中部三栏：C3 上线趋势 + C4 省域上线分布 + C5 项目联系人 -->
    <div class="grid grid-cols-rollout-mid gap-2.5 min-h-[220px] max-h-[260px] flex-shrink-0">
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

    <!-- C6: 单位台账表格与分页 -->
    <CockpitPanel
      title="单位台账"
      zone="C6"
      :subtitle="`共 ${filteredEntities.length} 家纳管单位`"
      class="flex-1 min-h-0"
    >
      <template #actions>
        <div class="flex items-center gap-2">
          <div class="relative flex items-center">
            <Search :size="13" class="absolute left-2.5 text-slate-400 pointer-events-none" />
            <input
              v-model="query"
              placeholder="搜索单位/联系人/批次/省份"
              class="pl-7 pr-2.5 py-1 text-cockpit-sm rounded-lg bg-surface-veil-03 border border-surface-veil-06 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-sky-500/40 w-52 transition-colors"
            />
          </div>
          <select
            v-model="selectedBatch"
            class="px-2.5 py-1 text-cockpit-sm rounded-lg bg-surface-veil-03 border border-surface-veil-06 text-slate-200 focus:outline-none focus:border-sky-500/40 transition-colors"
          >
            <option v-for="b in batchOptions" :key="b" :value="b">{{ b === '全部' ? '全部批次' : b }}</option>
          </select>
          <select
            v-model="selectedProvince"
            class="px-2.5 py-1 text-cockpit-sm rounded-lg bg-surface-veil-03 border border-surface-veil-06 text-slate-200 focus:outline-none focus:border-sky-500/40 transition-colors"
          >
            <option v-for="p in provinces" :key="p" :value="p">{{ p === '全部' ? '全部省份' : p }}</option>
          </select>
        </div>
      </template>

      <div class="flex flex-col h-full min-h-0 justify-between gap-2">
        <div class="flex-1 min-h-0 overflow-y-auto rounded-xl border border-surface-veil-06 bg-surface-veil-03">
          <table class="w-full border-collapse text-cockpit-sm">
            <thead>
              <tr>
                <th class="sticky top-0 bg-slate-900 px-3 py-2 text-left font-medium text-slate-400">编码 / 单位</th>
                <th class="sticky top-0 bg-slate-900 px-3 py-2 text-left font-medium text-slate-400">省份</th>
                <th class="sticky top-0 bg-slate-900 px-3 py-2 text-left font-medium text-slate-400">批次</th>
                <th class="sticky top-0 bg-slate-900 px-3 py-2 text-left font-medium text-slate-400">联系人</th>
                <th class="sticky top-0 bg-slate-900 px-3 py-2 text-left font-medium text-slate-400">状态</th>
                <th class="sticky top-0 bg-slate-900 px-3 py-2 text-left font-medium text-slate-400">建设进度</th>
                <th class="sticky top-0 bg-slate-900 px-3 py-2 text-right font-medium text-slate-400">期初数据</th>
                <th class="sticky top-0 bg-slate-900 px-3 py-2 text-right font-medium text-slate-400">凭证率</th>
                <th class="sticky top-0 bg-slate-900 px-3 py-2 text-left font-medium text-slate-400">更新时间</th>
                <th class="sticky top-0 bg-slate-900 px-3 py-2 text-center font-medium text-slate-400">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in paginatedEntities"
                :key="row.id"
                class="border-t border-surface-veil-06 text-slate-200 hover:bg-white/5 transition-colors"
              >
                <td class="px-3 py-1.5">
                  <div class="flex flex-col">
                    <b class="font-medium text-slate-100 truncate max-w-xs">{{ row.name }}</b>
                    <span class="font-mono text-cockpit-xs text-slate-500">MOD-{{ row.id }}</span>
                  </div>
                </td>
                <td class="px-3 py-1.5 text-slate-300">{{ row.province }}</td>
                <td class="px-3 py-1.5 text-slate-300">{{ row.batch }}</td>
                <td class="px-3 py-1.5 font-medium text-slate-300">
                  <span class="px-1.5 py-0.5 rounded bg-white/5 text-slate-300 border border-white/5">{{ row.owner }}</span>
                </td>
                <td class="px-3 py-1.5">
                  <span
                    class="px-2 py-0.5 rounded text-cockpit-xs font-medium border"
                    :class="{
                      'bg-emerald-950/40 text-emerald-400 border-emerald-500/30': row.status === '已上线',
                      'bg-sky-950/40 text-sky-400 border-sky-500/30': row.status === '双轨运行',
                      'bg-amber-950/40 text-amber-400 border-amber-500/30': row.status === '建设中',
                      'bg-slate-800/60 text-slate-400 border-white/10': row.status === '准备中',
                    }"
                  >
                    {{ row.status }}
                  </span>
                </td>
                <td class="px-3 py-1.5">
                  <div class="flex items-center gap-2">
                    <div class="w-16 h-1.5 rounded-full bg-slate-800 overflow-hidden">
                      <div class="h-full rounded-full bg-sky-400" :style="{ width: `${row.construction}%` }" />
                    </div>
                    <span class="font-mono text-cockpit-xs text-slate-300">{{ row.construction }}%</span>
                  </div>
                </td>
                <td class="px-3 py-1.5 text-right font-mono">{{ row.openingData }}%</td>
                <td class="px-3 py-1.5 text-right font-mono">{{ formatPercent(row.voucherRate) }}</td>
                <td class="px-3 py-1.5 text-slate-400 font-mono text-cockpit-xs">{{ row.updatedAt }}</td>
                <td class="px-3 py-1.5 text-center">
                  <button
                    class="px-2.5 py-0.5 rounded bg-sky-500/15 text-sky-400 border border-sky-500/30 hover:bg-sky-500/25 transition-colors text-cockpit-xs font-medium cursor-pointer"
                    @click="openEdit(row)"
                  >
                    调态
                  </button>
                </td>
              </tr>
              <tr v-if="!paginatedEntities.length">
                <td colspan="10" class="px-3 py-8 text-center text-slate-500">无匹配单位记录</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="flex items-center justify-between px-1 pt-1 text-cockpit-sm text-slate-400">
          <span>共 {{ filteredEntities.length }} 条 · 第 {{ page }} / {{ totalPages }} 页</span>
          <div class="flex items-center gap-2">
            <button
              :disabled="page <= 1"
              class="px-2.5 py-1 rounded bg-surface-veil-03 border border-surface-veil-06 text-slate-300 hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed transition-colors text-cockpit-xs cursor-pointer"
              @click="page--"
            >
              上一页
            </button>
            <button
              :disabled="page >= totalPages"
              class="px-2.5 py-1 rounded bg-surface-veil-03 border border-surface-veil-06 text-slate-300 hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed transition-colors text-cockpit-xs cursor-pointer"
              @click="page++"
            >
              下一页
            </button>
          </div>
        </div>
      </div>
    </CockpitPanel>

    <!-- 编辑抽屉 -->
    <div v-if="editing" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex justify-end" @click.self="editing = null">
      <aside class="w-96 h-full bg-slate-900 border-l border-white/10 p-5 flex flex-col gap-4 shadow-2xl overflow-y-auto">
        <header class="flex items-center justify-between border-b border-white/5 pb-3">
          <div>
            <span class="font-mono text-cockpit-xs text-sky-400 font-bold">MOD-{{ editing.id }}</span>
            <h3 class="text-cockpit-md font-semibold text-slate-100">调整单位状态</h3>
          </div>
          <button class="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-colors cursor-pointer" @click="editing = null">
            <X :size="18" />
          </button>
        </header>

        <div class="p-3 rounded-lg bg-surface-veil-03 border border-surface-veil-06">
          <b class="text-cockpit-md font-semibold text-slate-100 block">{{ editing.name }}</b>
          <span class="text-cockpit-sm text-slate-400 mt-1 block">{{ editing.province }} · {{ editing.batch }}</span>
        </div>

        <form class="flex flex-col gap-3.5 flex-1" @submit.prevent="save">
          <label class="flex flex-col gap-1 text-cockpit-sm text-slate-300 font-medium">
            运行状态
            <select
              v-model="draft.status"
              class="px-3 py-1.5 rounded-lg bg-slate-800 border border-white/10 text-slate-200 focus:outline-none focus:border-sky-500/40"
            >
              <option>准备中</option>
              <option>建设中</option>
              <option>双轨运行</option>
              <option>已上线</option>
            </select>
          </label>

          <label class="flex flex-col gap-1 text-cockpit-sm text-slate-300 font-medium">
            项目联系人
            <input
              v-model="draft.owner"
              class="px-3 py-1.5 rounded-lg bg-slate-800 border border-white/10 text-slate-200 focus:outline-none focus:border-sky-500/40"
            />
          </label>

          <label class="flex flex-col gap-1 text-cockpit-sm text-slate-300 font-medium">
            <div class="flex justify-between">
              <span>建设完成率</span>
              <b class="font-mono text-sky-400">{{ draft.construction }}%</b>
            </div>
            <input
              v-model.number="draft.construction"
              type="range"
              min="0"
              max="100"
              class="w-full accent-sky-400 cursor-pointer"
            />
          </label>

          <label class="flex flex-col gap-1 text-cockpit-sm text-slate-300 font-medium">
            <div class="flex justify-between">
              <span>期初数据完成率</span>
              <b class="font-mono text-emerald-400">{{ draft.openingData }}%</b>
            </div>
            <input
              v-model.number="draft.openingData"
              type="range"
              min="0"
              max="100"
              class="w-full accent-emerald-400 cursor-pointer"
            />
          </label>

          <p class="text-cockpit-xs text-slate-500 mt-auto">保存后即刻更新当前快照状态</p>

          <div class="flex items-center gap-2.5 pt-3 border-t border-white/5">
            <button
              type="button"
              class="flex-1 py-1.5 rounded-lg border border-white/10 text-slate-300 hover:bg-white/5 transition-colors text-cockpit-sm font-medium cursor-pointer"
              @click="editing = null"
            >
              取消
            </button>
            <button
              type="submit"
              class="flex-1 py-1.5 rounded-lg bg-sky-500 text-slate-950 font-semibold hover:bg-sky-400 transition-colors text-cockpit-sm cursor-pointer"
            >
              保存
            </button>
          </div>
        </form>
      </aside>
    </div>
  </div>
</template>
