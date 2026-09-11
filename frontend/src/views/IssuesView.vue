<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, GaugeChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import CockpitPanel from '../components/CockpitPanel.vue'
import PanelLegend from '../components/PanelLegend.vue'
import ChartBlock from '../components/blocks/ChartBlock.vue'
import CommandBand from '../components/blocks/CommandBand.vue'
import StatList from '../components/blocks/StatList.vue'
import type { StatRow } from '../components/blocks/types.ts'
import FilterSelect from '../components/ledger/FilterSelect.vue'
import LedgerPager from '../components/ledger/LedgerPager.vue'
import SearchInput from '../components/ledger/SearchInput.vue'
import { usePagedList } from '../composables/usePagedList.ts'
import ComplianceInspectDrawer, { type ComplianceIssueUnit } from '../components/ComplianceInspectDrawer.vue'
import LiveActivityTicker, { type GovernanceActivity } from '../components/LiveActivityTicker.vue'
import KioskSpotlightTour from '../components/KioskSpotlightTour.vue'
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
import { formatCount as format } from '../formatters/metrics.ts'
import { useProjectStore } from '../stores/project.ts'
import { createBatchComplianceOption } from '../charts/panelOptions.ts'
import { createComplianceOverviewOption } from '../charts/complianceOptions.ts'
import { BATCH_ORDER } from '../utils/entityOptions.ts'
import { COMPLIANCE_TAGS, deriveComplianceUnits } from '../utils/riskRules.ts'

const TAG_FILTER_OPTIONS = ['全部标签', ...COMPLIANCE_TAGS] as const

use([CanvasRenderer, BarChart, GaugeChart, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent])

const store = useProjectStore()

const searchQuery = ref('')
const selectedTag = ref<string>(TAG_FILTER_OPTIONS[0])
const inspectingUnit = ref<ComplianceIssueUnit | null>(null)
const activities = ref<GovernanceActivity[]>([])
const inspectingIssueId = ref<string>()
const inspectionNotice = ref('')
let inspectController: AbortController | null = null

function closeInspection() {
  inspectController?.abort()
  inspectingUnit.value = null
  inspectingIssueId.value = undefined
}
function inspectUnit(unit: ComplianceIssueUnit) {
  closeInspection()
  inspectingUnit.value = unit
}
async function inspectActivity(issueId: string) {
  closeInspection()
  inspectionNotice.value = ''
  const request = new AbortController()
  inspectController = request
  try {
    const response = await fetch(`${import.meta.env.BASE_URL}api/governance/issues/${encodeURIComponent(issueId)}`, { signal: request.signal })
    if (!response.ok) throw new Error('工单不可用')
    const issue = await response.json()
    if (request.signal.aborted) return
    const entity = store.entities.find(row => row.id === issue.unitId)
    if (!entity) throw new Error('当前快照未包含该单位，请刷新后查看')
    inspectingIssueId.value = issueId
    inspectingUnit.value = {
      ...entity, level: issue.severity === 'HIGH' ? '高' : '中',
      tags: [issue.issueType], primaryIssue: issue.title, detailNote: issue.description ?? '',
    }
  } catch (error) {
    if (!request.signal.aborted) inspectionNotice.value = error instanceof Error ? error.message : '工单读取失败'
  }
}
onUnmounted(() => inspectController?.abort())

// 矛与盾咬合：与 F 屏困难户共用 utils/riskRules 判定，仅依据真实运行指标派生标签
const complianceUnits = computed<ComplianceIssueUnit[]>(() =>
  deriveComplianceUnits(store.entities, store.snapshot.businessRules),
)

const totalUnits = computed(() => store.snapshot.overview.orgTotal ?? store.entities.length)
const compliantCount = computed(() => Math.max(0, totalUnits.value - complianceUnits.value.length))
const complianceRate = computed(() =>
  totalUnits.value > 0 ? ((compliantCount.value / totalUnits.value) * 100).toFixed(1) : null,
)

const highRiskCount = computed(() => complianceUnits.value.filter((u) => u.level === '高').length)
const mediumRiskCount = computed(() => complianceUnits.value.filter((u) => u.level === '中').length)

const tagDimensionCounts = computed(() => {
  const colors: Record<(typeof COMPLIANCE_TAGS)[number], string> = {
    超期挂账: chartSeriesColors[3],
    超预算迹象: chartSeriesColors[4],
    票据异常: chartSeriesColors[2],
    准备期卡顿: chartSeriesColors[1],
  }
  return COMPLIANCE_TAGS.map((label) => ({
    label,
    count: complianceUnits.value.filter((u) => u.tags.includes(label)).length,
    color: colors[label],
  }))
})

const complianceOverviewOption = computed(() => createComplianceOverviewOption({
  rate: complianceRate.value == null ? null : Number(complianceRate.value),
  supervised: complianceUnits.value.length,
  high: highRiskCount.value,
  medium: mediumRiskCount.value,
}))

const dominantComplianceTags = computed<StatRow[]>(() => [...tagDimensionCounts.value]
  .sort((a, b) => b.count - a.count)
  .slice(0, 3)
  .map((item) => ({ id: item.label, label: item.label, value: item.count })))

const tagBarOption = computed(() => ({
  ...calmAnimation,
  tooltip: { trigger: 'axis', ...chartTooltip },
  grid: { ...compactGrid, bottom: 18 },
  xAxis: { ...categoryAxis, data: tagDimensionCounts.value.map((t) => t.label), axisLabel: { ...categoryAxis.axisLabel, interval: 0, fontSize: 10 } },
  yAxis: valueAxis,
  series: [{ name: '涉及单位数', type: 'bar', data: tagDimensionCounts.value.map((t) => ({ value: t.count, itemStyle: { color: t.color } })), barWidth: '42%', barMaxWidth: 48, itemStyle: { borderRadius: [3, 3, 0, 0] } }],
}))

const riskPieOption = computed(() => ({
  ...calmAnimation,
  tooltip: { trigger: 'item', ...chartTooltip },
  legend: { orient: 'vertical', right: 10, top: 'center', textStyle: { color: chartInk.textMuted, fontSize: 11 }, itemWidth: 10, itemHeight: 10 },
  series: [{
    name: '合规水位构成', type: 'pie', radius: ['45%', '70%'], center: ['35%', '50%'],
    data: [
      { value: compliantCount.value, name: `合规达标 (${format(compliantCount.value)})`, itemStyle: { color: chartPalette.success } },
      { value: mediumRiskCount.value, name: `中度瑕疵 (${format(mediumRiskCount.value)})`, itemStyle: { color: chartPalette.warning } },
      { value: highRiskCount.value, name: `高风险隐患 (${format(highRiskCount.value)})`, itemStyle: { color: chartPalette.danger } },
    ],
    label: { show: false },
  }],
}))

const batchComplianceStats = computed(() =>
  BATCH_ORDER.map((name, idx) => {
    const batchUnits = store.entities.filter((e) => e.batch === name)
    const total = batchUnits.length
    const problemUnits = complianceUnits.value.filter((u) => u.batch === name)
    return {
      batchId: idx + 1, name, total, problemCount: problemUnits.length,
      complianceRate: total ? Number((((total - problemUnits.length) / total) * 100).toFixed(1)) : null,
      highCount: problemUnits.filter((u) => u.level === '高').length,
    }
  }),
)

const batchComplianceOption = computed(() => createBatchComplianceOption(batchComplianceStats.value))

const filteredTableUnits = computed(() =>
  complianceUnits.value.filter(
    (u) =>
      (selectedTag.value === TAG_FILTER_OPTIONS[0] || u.tags.includes(selectedTag.value)) &&
      (!searchQuery.value || `${u.name}${u.province}${u.batch}${u.owner}`.includes(searchQuery.value)),
  ),
)

const { page, totalPages: totalTablePages, items: paginatedTableUnits } = usePagedList(() => filteredTableUnits.value, {
  pageSize: 8,
  resetOn: [searchQuery, selectedTag],
})
</script>

<template>
  <div class="flex flex-col gap-2.5 h-full min-h-0 w-full" data-zone="E">
    <!-- E1: 合规仪表、风险分层与主要风险维度 -->
    <CockpitPanel
      title="合规监督指挥盘"
      zone="E1"
      :subtitle="`全网 ${format(totalUnits)} 家单位 · 合规水位、监督梯队与主要风险同屏`"
      class="flex-shrink-0"
    >
      <CommandBand>
        <template #chart>
          <VChart class="w-full h-full min-h-0" :option="complianceOverviewOption" autoresize />
        </template>
        <template #aside>
          <div class="flex items-center justify-between pb-1 border-b border-surface-veil-06 text-cockpit-xs"><span class="font-medium text-slate-300">主要风险维度</span><span class="text-slate-500">TOP 3</span></div>
          <StatList :rows="dominantComplianceTags" flat density="dense" />
        </template>
      </CommandBand>
    </CockpitPanel>

    <!-- GI #4 治理自愈动态广播流 -->
    <LiveActivityTicker class="flex-shrink-0" @activities="activities = $event" />
    <p v-if="inspectionNotice" role="status" class="text-cockpit-sm text-amber-400">{{ inspectionNotice }}</p>

    <!-- 中部：E2 风险维度分布 + E3 水位构成 (弹性优先，Guardrail 扩大为 min-h-[200px] max-h-[300px]，E-2) -->
    <div class="grid grid-cols-issues-top gap-2.5 min-h-[200px] max-h-[300px] flex-1">
      <CockpitPanel title="单位级合规风险标签分布" zone="E2" subtitle="挂账 / 预算 / 票据 三类真实指标维度">
        <VChart class="w-full h-full min-h-0" :option="tagBarOption" autoresize />
      </CockpitPanel>

      <CockpitPanel title="合规评级构成" zone="E3" subtitle="达标与监督梯队分布比例">
        <ChartBlock footnote="按当前快照单位指标计算，不预设合规率区间">
          <VChart :option="riskPieOption" autoresize />
        </ChartBlock>
      </CockpitPanel>
    </div>

    <!-- 下部：E4 用趋势与柱图替代 8 张横向小卡 -->
    <CockpitPanel title="各批次合规监督概览" zone="E4" subtitle="8 批次合规率与高风险单位分布" class="h-52 flex-shrink-0">
      <template #actions>
        <PanelLegend :items="[
          { label: '合规率', tone: 'success' },
          { label: '高风险', tone: 'danger' },
        ]" />
      </template>
      <VChart class="w-full h-full min-h-0" :option="batchComplianceOption" autoresize />
    </CockpitPanel>

    <!-- 底部：E5 重点监督单位台账与下钻 -->
    <CockpitPanel
      title="重点监督单位清单与问题下钻"
      zone="E5"
      subtitle="单位指标态现场判定（阈值派生） · 点击单位下钻查看治理工单处置流转"
      class="flex-1 min-h-0"
    >
      <template #actions>
        <div class="flex items-center gap-2 flex-wrap">
          <SearchInput v-model="searchQuery" placeholder="搜索单位/区域/联系人" />
          <FilterSelect v-model="selectedTag" :options="TAG_FILTER_OPTIONS" />
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

        <LedgerPager v-model="page" :total-pages="totalTablePages" :summary="`重点监督共 ${filteredTableUnits.length} 家`" />
      </div>
    </CockpitPanel>

    <!-- 下钻核查抽屉 -->
    <ComplianceInspectDrawer :unit="inspectingUnit" :issue-id="inspectingIssueId" @close="closeInspection" />

    <!-- 展厅无人巡航模式浮窗 -->
    <KioskSpotlightTour :activities="activities" :suspended="!!inspectingUnit" @inspect="inspectActivity" />
  </div>
</template>
