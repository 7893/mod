<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Info,
  Lock,
  RefreshCw,
  ShieldAlert,
  Sparkles,
} from 'lucide-vue-next'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, TitleComponent, TooltipComponent } from 'echarts/components'
import CockpitPanel from '../components/CockpitPanel.vue'
import BriefingList from '../components/blocks/BriefingList.vue'
import CommandBand from '../components/blocks/CommandBand.vue'
import EmptyNote from '../components/blocks/EmptyNote.vue'
import MetricGrid from '../components/blocks/MetricGrid.vue'
import NoteBanner from '../components/blocks/NoteBanner.vue'
import StatusList from '../components/blocks/StatusList.vue'
import type { BlockTone, MetricItem, StatusRow } from '../components/blocks/types.ts'
import ModelContractCard from '../components/ModelContractCard.vue'
import AtRiskUnitTable, { type AtRiskUnit } from '../components/AtRiskUnitTable.vue'
import AiQuotaCapsule from '../components/AiQuotaCapsule.vue'
import { describeExperimentalModel } from '../utils/modelEvaluation.ts'
import { useProjectStore } from '../stores/project.ts'
import { useInsightsStatus } from '../composables/useInsightsStatus.ts'
import { useDailyBriefing } from '../composables/useDailyBriefing.ts'
import {
  chartPalette,
  chartInk,
  chartTooltip,
  valueAxis,
  calmAnimation,
} from '../charts/theme.ts'
import { buildRiskDimensionBreakdown } from '../utils/qualityMetrics.ts'
import { deriveAtRiskUnits, indexPredictions } from '../utils/riskRules.ts'
import { parseBriefingSections } from '../utils/briefing.ts'
import { createRiskOverviewOption } from '../charts/insightsOptions.ts'

use([CanvasRenderer, BarChart, PieChart, GridComponent, TitleComponent, TooltipComponent])

const router = useRouter()
const store = useProjectStore()

const { status: insightsStatus } = useInsightsStatus()

// F5 每日决策简报（后台自动生成，只读展示，零交互）
const { briefing, loading: briefingLoading } = useDailyBriefing()
const BRIEFING_TONES: BlockTone[] = ['success', 'warning', 'accent']
const briefingSections = computed(() => parseBriefingSections(briefing.value?.content)
  .slice(0, 3)
  .map((section, index) => ({ ...section, tone: BRIEFING_TONES[index] ?? 'accent' })))

const predictionsMap = computed(() => indexPredictions(insightsStatus.value?.predictions))

// 风险主场核心：与 E 屏合规监督、生命周期推进器共用 utils/riskRules 同一判定标准
const atRiskUnits = computed<AtRiskUnit[]>(() =>
  deriveAtRiskUnits(store.entities, store.snapshot.businessRules, predictionsMap.value),
)

const dualDiffCount = computed(() => atRiskUnits.value.filter((u) => u.riskType === '双轨核对差异').length)
const constLagCount = computed(() => atRiskUnits.value.filter((u) => u.riskType === '建设严重滞后').length)
const prepStuckCount = computed(() => atRiskUnits.value.filter((u) => u.riskType === '准备期卡顿').length)

const riskDimensions = computed(() => buildRiskDimensionBreakdown(atRiskUnits.value, store.snapshot.businessRules))
const highRiskCount = computed(() => atRiskUnits.value.filter((u) => u.riskLevel === '高危').length)

const riskDistChartOption = computed(() => {
  const list = [...riskDimensions.value].reverse()
  const total = atRiskUnits.value.length

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
        const pct = total > 0 ? ((raw.count / total) * 100).toFixed(1) : '0.0'
        const batchKeys = Object.keys(raw.batchDistribution)
        const batchDetails = batchKeys.length
          ? batchKeys.map((k) => `${k} (${raw.batchDistribution[k]}家)`).join('、')
          : '暂无集中批次'

        return `
          <div style="font-size: 12px; line-height: 1.6;">
            <div style="font-weight: 600; color: ${chartInk.textPrimary}; margin-bottom: 4px;">${raw.type} · 高危 ${raw.highCount} / 关注 ${raw.count - raw.highCount}</div>
            <div style="color: ${chartInk.textMuted};">预警规模: <b style="color: ${chartInk.textPrimary}; font-family: monospace;">${raw.count} 家</b> (${pct}%)</div>
            <div style="color: ${chartInk.textMuted};">集中批次: <span style="color: ${chartInk.textPrimary};">${batchDetails}</span></div>
            <div style="color: ${chartInk.textMuted}; margin-top: 4px; border-top: 1px dashed ${chartInk.borderSoft}; padding-top: 4px;">门禁规则: ${raw.gate}</div>
          </div>
        `
      },
    },
    grid: {
      top: 10,
      bottom: 4,
      left: 80,
      right: 60,
      containLabel: true,
    },
    xAxis: {
      ...valueAxis,
      minInterval: 1,
      // 数值已标注在柱右侧，坐标轴刻度只会在窄宽度下互相重叠。
      axisLabel: { show: false },
      splitLine: {
        lineStyle: {
          color: chartInk.borderSoft,
          type: 'dashed',
        },
      },
    },
    yAxis: {
      type: 'category',
      data: list.map((i) => i.type),
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
        name: '单位数量',
        type: 'bar',
        barWidth: 12,
        data: list.map((item) => ({
          value: item.count,
          itemStyle: {
            borderRadius: [0, 4, 4, 0],
            color: item.tone === 'danger'
              ? chartPalette.danger
              : (item.tone === 'warning' ? chartPalette.warning : chartPalette.accent),
          },
        })),
        label: {
          show: true,
          position: 'right',
          color: chartInk.textPrimary,
          fontFamily: 'monospace',
          fontSize: 11,
          fontWeight: 'bold',
          formatter: '{c} 家',
        },
        showBackground: true,
        backgroundStyle: {
          color: chartInk.borderSoft,
          borderRadius: [0, 4, 4, 0],
        },
      },
    ],
  }
})

// KI-080: fit scores describe synthetic-label experiments, not validated future outcomes.
const insights = computed(() => {
  const hw = insightsStatus.value?.hw_ml
  const regQuality = hw?.models?.regression?.quality ?? null
  const clsQuality = hw?.models?.classifier?.quality ?? null
  return {
    targetModels: [
      describeExperimentalModel('REGRESSION', regQuality, hw?.models?.regression?.algorithm),
      describeExperimentalModel('CLASSIFICATION', clsQuality, hw?.models?.classifier?.algorithm),
    ],
    ruleBasedAlerts: store.snapshot.insights?.ruleBasedAlerts ?? [],
  }
})

const riskOverviewOption = computed(() => createRiskOverviewOption([
  { name: '双轨差异', value: dualDiffCount.value, color: chartPalette.danger },
  { name: '建设迟滞', value: constLagCount.value, color: chartPalette.warning },
  { name: '准备卡顿', value: prepStuckCount.value, color: chartPalette.accent },
]))

const riskUnitTotal = computed(() => dualDiffCount.value + constLagCount.value + prepStuckCount.value)

const modelQualityRows = computed(() => insights.value.targetModels.map((model) => {
  const quality = model.quality == null ? null : model.quality
  const progressQuality = quality == null ? 0 : Math.max(0, Math.min(1, quality))
  const regression = model.type === 'REGRESSION'
  return {
    label: regression ? '单量标签拟合' : '风险标签拟合',
    value: quality == null ? '—' : (regression ? `R² ${quality.toFixed(4)}` : `Acc ${(quality * 100).toFixed(1)}%`),
    progress: progressQuality * 100,
  }
}))

const evaluatedModelCount = computed(() => insights.value.targetModels.filter((model) => model.quality != null).length)

const riskHeadline = computed<MetricItem[]>(() => [
  { label: '风险单位', value: riskUnitTotal.value, tone: 'danger', hint: '三类风险合计' },
])

const ALERT_TONE: Record<string, BlockTone> = { SUCCESS: 'success', WARNING: 'warning' }
const ALERT_ICON: Record<string, typeof Info> = { SUCCESS: CheckCircle2, WARNING: AlertCircle }
const alertRows = computed<StatusRow[]>(() => insights.value.ruleBasedAlerts.map((alert) => ({
  id: alert.title,
  title: alert.title,
  desc: alert.detail,
  tone: ALERT_TONE[alert.level] ?? 'accent',
  icon: ALERT_ICON[alert.level] ?? Info,
})))
</script>

<template>
  <div class="flex flex-col gap-2.5 h-full min-h-0 w-full" data-zone="F">
    <!-- F1: 风险构成与模型质量门禁，替代四张等权指标卡 -->
    <CockpitPanel
      title="风险研判指挥盘"
      zone="F1"
      subtitle="规则风险构成与合成标签拟合分同屏"
      class="flex-shrink-0"
    >
      <CommandBand :chart-span="7">
        <template #chart>
          <div class="grid grid-cols-12 h-full min-h-0">
            <MetricGrid class="col-span-3 border-r border-surface-veil-06 pr-2" :items="riskHeadline" flat fill align="center" />
            <VChart class="col-span-9 w-full h-full min-h-0" :option="riskOverviewOption" autoresize />
          </div>
        </template>
        <template #aside>
          <div class="flex items-center justify-between pb-1 border-b border-surface-veil-06 text-cockpit-xs">
            <span class="font-medium text-slate-300">AutoML 实验评估</span>
            <b class="font-mono text-amber-400">{{ evaluatedModelCount }}/{{ insights.targetModels.length }} 已评估 · 非未来预测</b>
          </div>
          <div class="grid grid-rows-2 gap-1.5 flex-1 min-h-0 pt-1.5">
            <div v-for="model in modelQualityRows" :key="model.label" class="grid grid-cols-12 items-center gap-2 min-w-0">
              <span class="col-span-4 text-cockpit-xs text-slate-400 truncate">{{ model.label }}</span>
              <div class="col-span-5 h-1.5 rounded-full bg-white/5 overflow-hidden">
                <div class="h-full rounded-full bg-sky-400" :style="{ width: `${model.progress}%` }" />
              </div>
              <b class="col-span-3 font-mono text-cockpit-xs text-slate-200 text-right whitespace-nowrap">{{ model.value }}</b>
            </div>
          </div>
        </template>
      </CommandBand>
    </CockpitPanel>

    <!-- 主网格：F2-F5 (2x2 结构) -->
    <div class="grid grid-cols-insights grid-rows-insights gap-2.5 flex-1 min-h-0">
      <!-- 左上：F2 哪个单位要掉队 —— 困难户与掉队风险预警清单 (核心主场) -->
      <CockpitPanel
        title="哪个单位要掉队 · 困难户与掉队预警主场"
        zone="F2"
        subtitle="矛与盾读同一事实源 · 库内真实运行指标派生"
      >
        <AtRiskUnitTable :units="atRiskUnits" />
      </CockpitPanel>

      <!-- 右上：F4 HeatWave AutoML 预测模型 (严守 KI-023/KI-028 真实性) -->
      <CockpitPanel
        title="AutoML 模型实验与拟合评估"
        zone="F4"
        subtitle="合成标签实验 · 尚未验证未来预测能力"
      >
        <div class="flex flex-col h-full min-h-0 gap-2">
          <NoteBanner :icon="Lock" tone="warning">
            当前标签由规则生成 · 拟合分不代表未来预测能力
          </NoteBanner>


          <div class="grid grid-rows-2 gap-2 flex-1 min-h-0">
            <ModelContractCard :model="insights.targetModels[0]" empty-label="单位截面留出评估 · 非未来时间验证" :ready="false" />
            <ModelContractCard :model="insights.targetModels[1]" empty-label="随机单位留出评估 · 非实际延期标签" :ready="false" />
          </div>
        </div>
      </CockpitPanel>

      <!-- 左下：F3 综合态势预警与瓶颈排查 -->
      <CockpitPanel
        title="综合态势预警与瓶颈排查"
        zone="F3"
        subtitle="业务规则决定风险名单 · 模型仅补充特征"
      >
        <div class="grid grid-cols-12 gap-3 h-full min-h-0 items-stretch">
          <!-- 左侧：风险维度分布小图 (撑起空间，消除空旷感) -->
          <div class="col-span-5 flex flex-col h-full min-h-0 pr-3 border-r border-surface-veil-06">
            <div class="flex items-center justify-between pb-1.5 border-b border-surface-veil-06">
              <span class="text-cockpit-xs font-medium text-slate-300">困难户风险维度分布</span>
              <span class="font-mono text-cockpit-xs text-slate-400">共 {{ atRiskUnits.length }} 家预警</span>
            </div>
            <div class="flex-1 min-h-0 w-full">
              <VChart class="w-full h-full min-h-0" :option="riskDistChartOption" autoresize />
            </div>
            <div class="flex items-center justify-between pt-1 border-t border-surface-veil-06 text-cockpit-xs text-slate-500">
              <span>门禁：凭证率 &lt; {{ store.snapshot.businessRules.lifecycle.dualRunConsistencyRateMin }}% / 进度 &lt; {{ store.snapshot.businessRules.risk.constructionLagRate }}%</span>
              <span class="font-mono text-slate-400">{{ highRiskCount }} 家高危</span>
            </div>
          </div>

          <!-- 右侧：确定性规则告警 -->
          <div class="col-span-7 flex flex-col h-full min-h-0">
            <StatusList v-if="alertRows.length" :rows="alertRows" wrap />
            <EmptyNote v-else>暂无确定性规则告警</EmptyNote>
          </div>
        </div>
      </CockpitPanel>

      <!-- 右下：F5 每日指挥部决策简报（后台自动生成，只读展示，零交互） -->
      <CockpitPanel
        title="每日指挥部决策简报"
        zone="F5"
        subtitle="Cloudflare Workers AI · 每日自动生成 · 只读研判"
      >
        <template #actions>
          <div class="flex items-center gap-2">
            <AiQuotaCapsule />
            <span v-if="briefing?.briefingDate" class="font-mono text-cockpit-xs text-slate-500">{{ briefing.briefingDate }}</span>
          </div>
        </template>
        <div class="flex flex-col h-full min-h-0 gap-2">
          <NoteBanner :icon="ShieldAlert">{{ briefing?.isStale ? '历史简报 · 今日尚未更新，请勿作为当前态势' : 'AI 汇总摘要 · 原因与行动需另行核实' }}</NoteBanner>

          <div class="flex-1 min-h-0">
            <!-- 加载中 -->
            <div v-if="briefingLoading" class="flex flex-col items-center justify-center h-full rounded-xl bg-surface-veil-03 border border-surface-veil-06 text-center gap-2 py-4 text-slate-500">
              <RefreshCw :size="18" class="animate-spin opacity-50 text-sky-400" />
              <span class="text-cockpit-xs">正在读取每日简报…</span>
            </div>

            <!-- 已有简报：纵向分节、全文展示，不截断 -->
            <BriefingList v-else-if="briefing?.status === 'ok'" class="h-full min-h-0 overflow-y-auto" :sections="briefingSections" />

            <!-- 尚无简报（定时任务未生成） -->
            <div v-else class="flex flex-col items-center justify-center h-full rounded-xl bg-surface-veil-03 border border-surface-veil-06 text-center gap-1.5 py-4 text-slate-400">
              <div class="w-8 h-8 rounded-full bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 mb-0.5">
                <Sparkles :size="15" />
              </div>
              <span class="text-cockpit-sm font-semibold text-slate-200">每日简报待生成</span>
              <span class="text-cockpit-xs text-slate-500">后台定时任务每日 00:30 自动生成研判简报</span>
            </div>
          </div>

          <!-- 联动直达按钮 -->
          <div class="flex items-center gap-2 pt-1 border-t border-surface-veil-06 flex-shrink-0">
            <button
              type="button"
              class="flex-1 flex items-center justify-between px-2.5 py-1 rounded-lg bg-surface-veil-03 border border-surface-veil-06 text-slate-300 hover:text-white hover:bg-white/5 transition-colors text-cockpit-xs font-medium cursor-pointer"
              @click="router.push('/b?tab=ledger')"
            >
              <span>查看建设进度台账</span>
              <ArrowRight :size="12" />
            </button>
            <button
              type="button"
              class="flex-1 flex items-center justify-between px-2.5 py-1 rounded-lg bg-surface-veil-03 border border-surface-veil-06 text-slate-300 hover:text-white hover:bg-white/5 transition-colors text-cockpit-xs font-medium cursor-pointer"
              @click="router.push('/e')"
            >
              <span>查看合规监督态势</span>
              <ArrowRight :size="12" />
            </button>
          </div>
        </div>
      </CockpitPanel>
    </div>
  </div>
</template>
