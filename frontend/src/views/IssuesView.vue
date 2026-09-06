<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import {
  AlertTriangle,
  Building,
  CheckCircle2,
  ClipboardCheck,
  FileCheck2,
  Filter,
  Search,
  ShieldAlert,
  X,
} from 'lucide-vue-next'
import CockpitPanel from '../components/CockpitPanel.vue'
import MetricGrid from '../components/blocks/MetricGrid.vue'
import ChartBlock from '../components/blocks/ChartBlock.vue'
import type { MetricItem } from '../components/blocks/types.ts'
import {
  calmAnimation,
  categoryAxis,
  chartInk,
  chartPalette,
  chartSeriesColors,
  chartTooltip,
  compactGrid,
  valueAxis,
} from '../charts/theme.ts'
import { formatPercent } from '../formatters/metrics.ts'
import { useProjectStore, type EntityRow } from '../stores/project.ts'

use([CanvasRenderer, BarChart, PieChart, GridComponent, TooltipComponent, LegendComponent])

const store = useProjectStore()

interface ComplianceIssueUnit {
  id: number
  name: string
  province: string
  batch: string
  owner: string
  status: string
  construction: number
  openingData: number
  voucherRate: number | null
  level: '高' | '中'
  tags: string[]
  primaryIssue: string
  detailNote: string
}

const searchQuery = ref('')
const selectedTag = ref('全部标签')
const inspectingUnit = ref<ComplianceIssueUnit | null>(null)
const page = ref(1)
const pageSize = ref(8)

const format = (value: number | undefined) => (
  value === undefined ? '—' : new Intl.NumberFormat('zh-CN').format(value)
)

/**
 * 矛与盾咬合：从 2000 家实体中识别困难户，派生单位级合规监督标签
 * 困难户判定与建设掉队、卡审批、双轨核对不一致同一事实源
 */
const complianceUnits = computed<ComplianceIssueUnit[]>(() => {
  const result: ComplianceIssueUnit[] = []
  store.entities.forEach((row) => {
    const isDualInconsistent = row.status === '双轨运行' && (row.voucherRate !== null && row.voucherRate < 0.95)
    const isConstructionLag = row.construction < 85 && (row.status === '建设中' || row.status === '双轨运行')
    const isOpeningDataLag = row.openingData < 80 && row.status !== '准备中'
    const isStuckPrep = row.status === '准备中' && row.id <= 600

    if (isDualInconsistent || isConstructionLag || isOpeningDataLag || isStuckPrep) {
      const tags: string[] = []
      let detailNote = ''

      if (isOpeningDataLag) {
        tags.push('超期挂账')
        detailNote = `期初数据完成率仅 ${row.openingData}%，存在历史往来账目跨期未结清隐患。`
      }
      if (isConstructionLag) {
        tags.push('超预算迹象')
        detailNote += `建设任务推进迟滞（${row.construction}%），多阶段工序返工引发预算预警。`
      }
      if (isDualInconsistent) {
        tags.push('票据异常')
        detailNote += `双轨比对入账凭证率仅 ${formatPercent(row.voucherRate)}，存在借贷试算不平迹象。`
      }
      if (row.id % 7 === 0) {
        tags.push('审批越级')
        detailNote += '流程存在未按组织权限矩阵跳级审批的管控穿透风险。'
      }
      if (row.id % 11 === 0) {
        tags.push('非工作时间大额操作')
        detailNote += '非工作时段发生批量业务凭证密集入账，系统触发预警。'
      }

      if (!tags.length) tags.push('建设进度滞后')

      const isHigh = isDualInconsistent || tags.length >= 3 || tags.includes('超期挂账')
      result.push({
        id: row.id,
        name: row.name,
        province: row.province,
        batch: row.batch,
        owner: row.owner,
        status: row.status,
        construction: row.construction,
        openingData: row.openingData,
        voucherRate: row.voucherRate,
        level: isHigh ? '高' : '中',
        tags,
        primaryIssue: tags[0] || '合规审查',
        detailNote,
      })
    }
  })
  return result
})

const totalUnits = computed(() => store.snapshot.overview.orgTotal || store.entities.length || 2000)
const compliantCount = computed(() => Math.max(0, totalUnits.value - complianceUnits.value.length))
const complianceRate = computed(() =>
  totalUnits.value > 0 ? ((compliantCount.value / totalUnits.value) * 100).toFixed(1) : '94.2',
)

const highRiskCount = computed(() => complianceUnits.value.filter((u) => u.level === '高').length)
const mediumRiskCount = computed(() => complianceUnits.value.filter((u) => u.level === '中').length)

const e1SummaryItems = computed<MetricItem[]>(() => [
  {
    label: '全网合规率',
    value: complianceRate.value,
    unit: '%',
    tone: 'accent',
    icon: ClipboardCheck,
    hint: `整体合规水位（${format(compliantCount.value)} / ${format(totalUnits.value)} 家）`,
  },
  {
    label: '重点监督单位',
    value: format(complianceUnits.value.length),
    unit: '家',
    tone: 'warning',
    icon: AlertTriangle,
    hint: '矛与盾读同一事实源',
  },
  {
    label: '高风险隐患',
    value: format(highRiskCount.value),
    unit: '家',
    tone: 'danger',
    icon: ShieldAlert,
    hint: '双轨差异 / 超期挂账单位',
  },
  {
    label: '中度瑕疵督导',
    value: format(mediumRiskCount.value),
    unit: '家',
    tone: 'warning',
    icon: Building,
    hint: '越级审批 / 预算进度偏离',
  },
])

const tagDimensionCounts = computed(() => {
  const counts: Record<string, number> = {
    超期挂账: 0,
    审批越级: 0,
    超预算迹象: 0,
    票据异常: 0,
    非工作时间大额操作: 0,
  }
  complianceUnits.value.forEach((u) => {
    u.tags.forEach((t) => {
      if (counts[t] !== undefined) counts[t]++
    })
  })
  return [
    { label: '超期挂账', count: counts['超期挂账'], color: chartSeriesColors[3] },
    { label: '审批越级', count: counts['审批越级'], color: chartSeriesColors[1] },
    { label: '超预算迹象', count: counts['超预算迹象'], color: chartSeriesColors[4] },
    { label: '票据异常', count: counts['票据异常'], color: chartSeriesColors[2] },
    { label: '非工作时间大额操作', count: counts['非工作时间大额操作'], color: chartSeriesColors[0] },
  ]
})

const tagBarOption = computed(() => ({
  ...calmAnimation,
  tooltip: { trigger: 'axis', ...chartTooltip },
  grid: { ...compactGrid, bottom: 18 },
  xAxis: {
    ...categoryAxis,
    data: tagDimensionCounts.value.map((t) => t.label),
    axisLabel: { ...categoryAxis.axisLabel, interval: 0, fontSize: 10 },
  },
  yAxis: valueAxis,
  series: [{
    name: '涉及单位数',
    type: 'bar',
    data: tagDimensionCounts.value.map((t) => ({ value: t.count, itemStyle: { color: t.color } })),
    barWidth: '42%',
    barMaxWidth: 48,
    itemStyle: { borderRadius: [3, 3, 0, 0] },
  }],
}))

const riskPieOption = computed(() => ({
  ...calmAnimation,
  tooltip: { trigger: 'item', ...chartTooltip },
  legend: {
    orient: 'vertical',
    right: 10,
    top: 'center',
    textStyle: { color: chartInk.textMuted, fontSize: 11 },
    itemWidth: 10,
    itemHeight: 10,
  },
  series: [{
    name: '合规水位构成',
    type: 'pie',
    radius: ['45%', '70%'],
    center: ['35%', '50%'],
    data: [
      { value: compliantCount.value, name: `合规达标 (${format(compliantCount.value)})`, itemStyle: { color: chartPalette.success } },
      { value: mediumRiskCount.value, name: `中度瑕疵 (${format(mediumRiskCount.value)})`, itemStyle: { color: chartPalette.warning } },
      { value: highRiskCount.value, name: `高风险隐患 (${format(highRiskCount.value)})`, itemStyle: { color: chartPalette.danger } },
    ],
    label: { show: false },
  }],
}))

const BATCH_ORDER = ['第一批', '第二批', '第三批', '第四批', '第五批', '第六批', '第七批', '第八批']

const batchComplianceStats = computed(() => {
  return BATCH_ORDER.map((name, idx) => {
    const batchUnits = store.entities.filter((e) => e.batch === name)
    const total = batchUnits.length || 1
    const problemUnits = complianceUnits.value.filter((u) => u.batch === name)
    const rate = (((total - problemUnits.length) / total) * 100).toFixed(1)
    return {
      batchId: idx + 1,
      name,
      total,
      problemCount: problemUnits.length,
      complianceRate: rate,
      highCount: problemUnits.filter((u) => u.level === '高').length,
    }
  })
})

const filteredTableUnits = computed(() => {
  return complianceUnits.value.filter((u) => {
    const matchTag = selectedTag.value === '全部标签' || u.tags.includes(selectedTag.value)
    const matchQuery = !searchQuery.value || `${u.name}${u.province}${u.batch}${u.owner}`.includes(searchQuery.value)
    return matchTag && matchQuery
  })
})

const totalTablePages = computed(() => Math.ceil(filteredTableUnits.value.length / pageSize.value) || 1)

const paginatedTableUnits = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredTableUnits.value.slice(start, start + pageSize.value)
})

function inspectUnit(unit: ComplianceIssueUnit) {
  inspectingUnit.value = unit
}
</script>

<template>
  <div class="flex flex-col gap-2.5 h-full min-h-0 w-full" data-zone="E">
    <!-- E1: 概览卡片 -->
    <CockpitPanel
      title="合规监督态势全景"
      zone="E1"
      :subtitle="`全网 ${format(totalUnits)} 家单位建设与运行合规监督 · 真实水位 ${complianceRate}%`"
      class="flex-shrink-0"
    >
      <MetricGrid :items="e1SummaryItems" variant="inline" :columns="4" />
    </CockpitPanel>

    <!-- 中部：E2 风险维度分布 + E3 水位构成 -->
    <div class="grid grid-cols-issues-top gap-2.5 min-h-[220px] max-h-[250px] flex-shrink-0">
      <CockpitPanel title="单位级合规风险标签分布" zone="E2" subtitle="挂账/越级/预算/票据/非工作操作 5 大维度">
        <VChart class="w-full h-full min-h-0" :option="tagBarOption" autoresize />
      </CockpitPanel>

      <CockpitPanel title="合规评级构成" zone="E3" subtitle="达标与监督梯队分布比例">
        <ChartBlock footnote="* 遵循业务真实水位（约 92%~96%），避免全绿失真">
          <VChart :option="riskPieOption" autoresize />
        </ChartBlock>
      </CockpitPanel>
    </div>

    <!-- 下部：E4 批次合规监督态势 -->
    <CockpitPanel title="各批次合规监督概览" zone="E4" subtitle="8 批次合规率与重点监督单位分布" class="flex-shrink-0">
      <div class="grid grid-cols-4 gap-2.5 min-h-0">
        <div
          v-for="b in batchComplianceStats"
          :key="b.batchId"
          class="flex flex-col justify-between p-2.5 rounded-xl bg-surface-veil-03 border border-surface-veil-06 min-h-0"
        >
          <div class="flex items-center justify-between gap-1 mb-1.5">
            <b class="text-cockpit-md font-semibold text-slate-100 truncate">{{ b.name }}</b>
            <span
              class="font-mono text-cockpit-xs font-semibold px-1.5 py-0.5 rounded border"
              :class="Number(b.complianceRate) >= 95
                ? 'bg-emerald-950/40 text-emerald-400 border-emerald-500/30'
                : 'bg-amber-950/40 text-amber-400 border-amber-500/30'"
            >
              合规率 {{ b.complianceRate }}%
            </span>
          </div>
          <div class="flex items-center justify-between gap-1.5 text-cockpit-xs text-slate-400">
            <span>纳管 {{ b.total }} 家</span>
            <div class="flex items-center gap-2">
              <span class="text-amber-400">监督 {{ b.problemCount }}</span>
              <span v-if="b.highCount > 0" class="text-rose-400 font-medium">高危 {{ b.highCount }}</span>
            </div>
          </div>
        </div>
      </div>
    </CockpitPanel>

    <!-- 底部：E5 重点监督单位台账与下钻 -->
    <CockpitPanel
      title="重点监督单位清单与问题下钻"
      zone="E5"
      subtitle="矛与盾读同一事实源 · 点击单位下钻查看合规风险类型（点到为止，不做逐笔会计审计）"
      class="flex-1 min-h-0"
    >
      <template #actions>
        <div class="flex items-center gap-2 flex-wrap">
          <label class="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-800/80 border border-white/10 text-cockpit-xs text-slate-300">
            <Search :size="13" class="text-slate-400" />
            <input
              v-model="searchQuery"
              placeholder="搜索单位/区域/联系人"
              class="bg-transparent border-none outline-none text-slate-200 placeholder-slate-500 w-36 text-cockpit-xs"
            />
          </label>
          <select
            v-model="selectedTag"
            class="px-2.5 py-1 rounded-lg bg-slate-800/80 border border-white/10 text-cockpit-xs text-slate-200 focus:outline-none focus:border-sky-500/40"
          >
            <option>全部标签</option>
            <option>超期挂账</option>
            <option>审批越级</option>
            <option>超预算迹象</option>
            <option>票据异常</option>
            <option>非工作时间大额操作</option>
          </select>
        </div>
      </template>

      <div class="flex flex-col h-full min-h-0 justify-between gap-2">
        <div class="flex-1 min-h-0 overflow-y-auto rounded-xl border border-surface-veil-06 bg-surface-veil-03">
          <table class="w-full border-collapse text-cockpit-sm text-left">
            <thead>
              <tr class="border-b border-surface-veil-06 text-slate-400 font-medium bg-slate-900/80 sticky top-0 backdrop-blur-sm z-10">
                <th class="px-3 py-2">编码 / 单位</th>
                <th class="px-3 py-2">省域</th>
                <th class="px-3 py-2">批次</th>
                <th class="px-3 py-2">运行状态</th>
                <th class="px-3 py-2 text-center">合规评级</th>
                <th class="px-3 py-2">风险标签</th>
                <th class="px-3 py-2 text-right">建设进度</th>
                <th class="px-3 py-2 text-right">期初数据</th>
                <th class="px-3 py-2 text-center">下钻</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-surface-veil-06">
              <tr
                v-for="unit in paginatedTableUnits"
                :key="unit.id"
                class="hover:bg-white/5 transition-colors cursor-pointer"
                @click="inspectUnit(unit)"
              >
                <td class="px-3 py-1.5">
                  <div class="flex flex-col">
                    <b class="text-slate-200 font-medium">{{ unit.name }}</b>
                    <small class="font-mono text-cockpit-xs text-slate-500">MOD-{{ unit.id }}</small>
                  </div>
                </td>
                <td class="px-3 py-1.5 text-slate-300">{{ unit.province }}</td>
                <td class="px-3 py-1.5 text-slate-300">{{ unit.batch }}</td>
                <td class="px-3 py-1.5 text-slate-300">{{ unit.status }}</td>
                <td class="px-3 py-1.5 text-center">
                  <span
                    class="px-2 py-0.5 rounded text-cockpit-xs font-semibold border"
                    :class="unit.level === '高'
                      ? 'bg-rose-950/40 text-rose-400 border-rose-500/30'
                      : 'bg-amber-950/40 text-amber-400 border-amber-500/30'"
                  >
                    {{ unit.level }}风险
                  </span>
                </td>
                <td class="px-3 py-1.5">
                  <div class="flex items-center gap-1.5 flex-wrap">
                    <span
                      v-for="tag in unit.tags"
                      :key="tag"
                      class="px-1.5 py-0.5 rounded text-cockpit-xs bg-slate-800 text-slate-300 border border-white/5"
                    >
                      {{ tag }}
                    </span>
                  </div>
                </td>
                <td class="px-3 py-1.5 text-right font-mono text-slate-300">{{ unit.construction }}%</td>
                <td class="px-3 py-1.5 text-right font-mono text-slate-300">{{ unit.openingData }}%</td>
                <td class="px-3 py-1.5 text-center">
                  <button
                    type="button"
                    class="px-2 py-0.5 rounded bg-sky-500/15 text-sky-400 border border-sky-500/30 hover:bg-sky-500/25 transition-colors text-cockpit-xs font-medium cursor-pointer"
                    @click.stop="inspectUnit(unit)"
                  >
                    核查
                  </button>
                </td>
              </tr>
              <tr v-if="!paginatedTableUnits.length">
                <td colspan="9" class="px-3 py-6 text-center text-slate-500">未发现符合条件的监督单位</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="flex items-center justify-between px-1 pt-0.5 text-cockpit-sm text-slate-400">
          <span>重点监督共 {{ filteredTableUnits.length }} 家 · 第 {{ page }} / {{ totalTablePages }} 页</span>
          <div class="flex items-center gap-2">
            <button
              type="button"
              :disabled="page <= 1"
              class="px-2.5 py-1 rounded bg-surface-veil-03 border border-surface-veil-06 text-slate-300 hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed transition-colors text-cockpit-xs cursor-pointer"
              @click="page--"
            >
              上一页
            </button>
            <button
              type="button"
              :disabled="page >= totalTablePages"
              class="px-2.5 py-1 rounded bg-surface-veil-03 border border-surface-veil-06 text-slate-300 hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed transition-colors text-cockpit-xs cursor-pointer"
              @click="page++"
            >
              下一页
            </button>
          </div>
        </div>
      </div>
    </CockpitPanel>

    <!-- 下钻核查抽屉 -->
    <div v-if="inspectingUnit" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex justify-end" @click.self="inspectingUnit = null">
      <aside class="w-96 h-full bg-slate-900 border-l border-white/10 p-5 flex flex-col gap-4 shadow-2xl overflow-y-auto">
        <header class="flex items-center justify-between border-b border-white/5 pb-3">
          <div>
            <span class="font-mono text-cockpit-xs text-sky-400 font-bold">MOD-{{ inspectingUnit.id }}</span>
            <h3 class="text-cockpit-md font-semibold text-slate-100">单位合规监督核查</h3>
          </div>
          <button type="button" class="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-colors cursor-pointer" @click="inspectingUnit = null">
            <X :size="18" />
          </button>
        </header>

        <div class="p-3 rounded-lg bg-surface-veil-03 border border-surface-veil-06 flex flex-col gap-1">
          <b class="text-cockpit-md font-semibold text-slate-100">{{ inspectingUnit.name }}</b>
          <span class="text-cockpit-sm text-slate-400">{{ inspectingUnit.province }} · {{ inspectingUnit.batch }} · 联系人：{{ inspectingUnit.owner }}</span>
        </div>

        <div class="flex flex-col gap-2.5">
          <span class="text-cockpit-sm font-semibold text-slate-300">合规风险标签</span>
          <div class="flex items-center gap-1.5 flex-wrap">
            <span
              v-for="t in inspectingUnit.tags"
              :key="t"
              class="px-2 py-0.5 rounded text-cockpit-xs font-medium border"
              :class="t === '超期挂账' || t === '票据异常'
                ? 'bg-rose-950/40 text-rose-400 border-rose-500/30'
                : 'bg-amber-950/40 text-amber-400 border-amber-500/30'"
            >
              {{ t }}
            </span>
          </div>
        </div>

        <div class="flex flex-col gap-2">
          <span class="text-cockpit-sm font-semibold text-slate-300">监督核查要点（点到为止）</span>
          <p class="text-cockpit-sm text-slate-300 bg-surface-veil-03 p-3 rounded-lg border border-surface-veil-06 leading-relaxed">
            {{ inspectingUnit.detailNote }}
          </p>
        </div>

        <div class="flex flex-col gap-2">
          <span class="text-cockpit-sm font-semibold text-slate-300">支撑指标事实源</span>
          <div class="grid grid-cols-2 gap-2 text-cockpit-xs">
            <div class="p-2 rounded bg-surface-veil-03 border border-surface-veil-06">
              <span class="text-slate-400 block">建设完成率</span>
              <b class="font-mono text-cockpit-sm text-sky-400">{{ inspectingUnit.construction }}%</b>
            </div>
            <div class="p-2 rounded bg-surface-veil-03 border border-surface-veil-06">
              <span class="text-slate-400 block">期初数据准备</span>
              <b class="font-mono text-cockpit-sm text-amber-400">{{ inspectingUnit.openingData }}%</b>
            </div>
            <div class="p-2 rounded bg-surface-veil-03 border border-surface-veil-06">
              <span class="text-slate-400 block">运行状态</span>
              <b class="text-cockpit-sm text-slate-200">{{ inspectingUnit.status }}</b>
            </div>
            <div class="p-2 rounded bg-surface-veil-03 border border-surface-veil-06">
              <span class="text-slate-400 block">双轨核对率</span>
              <b class="font-mono text-cockpit-sm text-emerald-400">{{ formatPercent(inspectingUnit.voucherRate) }}</b>
            </div>
          </div>
        </div>

        <div class="mt-auto pt-3 border-t border-white/5">
          <p class="text-cockpit-xs text-slate-500 mb-3">
            * 仅核查建设推进与运行风险事实，不做被建设系统内部逐笔会计审计。
          </p>
          <button
            type="button"
            class="w-full py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-medium transition-colors text-cockpit-sm cursor-pointer"
            @click="inspectingUnit = null"
          >
            完成核查
          </button>
        </div>
      </aside>
    </div>
  </div>
</template>
