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
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, TitleComponent, TooltipComponent } from 'echarts/components'
import CockpitPanel from '../components/CockpitPanel.vue'
import ChartCanvas from '../components/charts/ChartCanvas.vue'
import BriefingList from '../components/blocks/BriefingList.vue'
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
import { buildRiskDimensionBreakdown } from '../utils/qualityMetrics.ts'
import { deriveAtRiskUnits, indexPredictions } from '../utils/riskRules.ts'
import { parseBriefingSections } from '../utils/briefing.ts'
import { createRiskDimensionOption } from '../charts/insightsOptions.ts'

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

const riskDimensions = computed(() => buildRiskDimensionBreakdown(atRiskUnits.value, store.snapshot.businessRules))
const highRiskCount = computed(() => atRiskUnits.value.filter((u) => u.riskLevel === '高危').length)

const riskDistChartOption = computed(() => createRiskDimensionOption(
  riskDimensions.value,
  atRiskUnits.value.length,
))

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

const ALERT_TONE: Record<string, BlockTone> = { SUCCESS: 'success', WARNING: 'warning' }
const ALERT_ICON: Record<string, typeof Info> = { SUCCESS: CheckCircle2, WARNING: AlertCircle }
const alertRows = computed<StatusRow[]>(() => insights.value.ruleBasedAlerts.map((alert) => ({
  id: alert.title,
  title: alert.title,
  desc: alert.detail,
  tone: ALERT_TONE[alert.level] ?? 'accent',
  icon: ALERT_ICON[alert.level] ?? Info,
})))

const primaryRiskDimension = computed(() => {
  const sorted = [...riskDimensions.value].sort((left, right) => right.count - left.count)
  return sorted[0]?.count ? sorted[0] : null
})

const decisionItems = computed<MetricItem[]>(() => {
  const primary = primaryRiskDimension.value
  return [
    {
      label: '首要瓶颈',
      value: primary?.type ?? '暂无集中风险',
      tone: primary?.tone ?? 'success',
      hint: primary?.gate ?? '当前规则未识别集中风险',
    },
    { label: '影响单位', value: primary?.count ?? 0, unit: '家', tone: primary?.tone ?? 'success' },
    { label: '其中高危', value: primary?.highCount ?? 0, unit: '家', tone: primary?.highCount ? 'danger' : 'success' },
    { label: '规则告警', value: alertRows.value.length, unit: '项', tone: alertRows.value.length ? 'warning' : 'success' },
  ]
})
</script>

<template>
  <div class="flex flex-col gap-2.5 h-full min-h-0 w-full" data-zone="F">
    <!-- F1: 只给出当前决策优先级，风险分布与模型质量分别留在 F3/F4 -->
    <CockpitPanel
      title="风险决策摘要"
      zone="F1"
      subtitle="首要瓶颈与行动优先级 · 不重复风险分布和模型评分"
      class="flex-shrink-0"
    >
      <MetricGrid :items="decisionItems" :columns="4" flat fill size="lg" align="center" />
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
              <ChartCanvas :option="riskDistChartOption" />
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
        subtitle="Cloudflare Workers AI · 上一完整自然日 · 只读研判"
      >
        <template #actions>
          <div class="flex items-center gap-2">
            <AiQuotaCapsule />
            <span v-if="briefing?.briefingDate" class="font-mono text-cockpit-xs text-slate-500">{{ briefing.briefingDate }}</span>
          </div>
        </template>
        <div class="flex flex-col h-full min-h-0 gap-2">
          <NoteBanner :icon="ShieldAlert">{{ briefing?.isStale ? '历史日报 · 上一完整自然日尚未生成，请勿作为最新日报' : '上一完整自然日 AI 摘要 · 当前实时态势以大盘指标为准' }}</NoteBanner>

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
