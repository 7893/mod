<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Building,
  CheckCircle2,
  Database,
  HelpCircle,
  Info,
  Lock,
  RefreshCw,
  ShieldAlert,
  Sparkles,
} from 'lucide-vue-next'
import CockpitPanel from '../components/CockpitPanel.vue'
import MetricGrid from '../components/blocks/MetricGrid.vue'
import type { MetricItem } from '../components/blocks/types.ts'
import ModelContractCard from '../components/ModelContractCard.vue'
import MarkdownLite from '../components/MarkdownLite.vue'
import AtRiskUnitTable, { type AtRiskUnit } from '../components/AtRiskUnitTable.vue'
import { formatPercent } from '../formatters/metrics.ts'
import { useProjectStore } from '../stores/project.ts'
import { useAiInsights } from '../composables/useAiInsights.ts'

const router = useRouter()
const store = useProjectStore()

const format = (value: number | undefined) => (
  value === undefined ? '—' : new Intl.NumberFormat('zh-CN').format(value)
)

/**
 * 风险主场核心：从真实实体指标中筛选困难户（矛与盾读同一事实源）
 * 与生命周期推进器 (Advancer) 和合规监督 (Issues) 统一判定标准
 */
const atRiskUnits = computed<AtRiskUnit[]>(() => {
  const list: AtRiskUnit[] = []
  store.entities.forEach((row) => {
    const isDualDiff = row.status === '双轨运行' && (row.voucherRate !== null && row.voucherRate < 95)
    const isConstructionLag = row.construction < 88 && (row.status === '建设中' || row.status === '双轨运行')
    const isPrepStuck = row.status === '准备中' && (row.batchId ? row.batchId <= 6 : row.id <= 1000)

    if (isDualDiff) {
      list.push({
        id: row.id,
        name: row.name,
        province: row.province,
        batch: row.batch,
        owner: row.owner,
        status: row.status,
        construction: row.construction,
        openingData: row.openingData,
        voucherRate: row.voucherRate,
        riskType: '双轨核对差异',
        riskLevel: '高危',
        reason: `双轨入账凭证率仅 ${formatPercent(row.voucherRate)}，未达 95% 门禁，存在借贷试算不平风险`,
      })
    } else if (isConstructionLag) {
      list.push({
        id: row.id,
        name: row.name,
        province: row.province,
        batch: row.batch,
        owner: row.owner,
        status: row.status,
        construction: row.construction,
        openingData: row.openingData,
        voucherRate: row.voucherRate,
        riskType: '建设严重滞后',
        riskLevel: row.construction < 80 ? '高危' : '重点关注',
        reason: `建设完成度 (${row.construction}%) 显著落后于批次推进均值，存在阶段脱轨掉队风险`,
      })
    } else if (isPrepStuck) {
      list.push({
        id: row.id,
        name: row.name,
        province: row.province,
        batch: row.batch,
        owner: row.owner,
        status: row.status,
        construction: row.construction,
        openingData: row.openingData,
        voucherRate: row.voucherRate,
        riskType: '准备期卡顿',
        riskLevel: '重点关注',
        reason: '属于已推进批次但仍停留在准备中，期初数据收集或基础环境尚未打通',
      })
    }
  })
  return list
})

const dualDiffCount = computed(() => atRiskUnits.value.filter((u) => u.riskType === '双轨核对差异').length)
const constLagCount = computed(() => atRiskUnits.value.filter((u) => u.riskType === '建设严重滞后').length)
const prepStuckCount = computed(() => atRiskUnits.value.filter((u) => u.riskType === '准备期卡顿').length)

const {
  aiPhase,
  aiLatest,
  aiGenerating,
  aiButtonLabel,
  aiButtonDisabled,
  generatedAt,
  triggerGenerate,
} = useAiInsights()

/**
 * 严守 KI-023/KI-028 规范：
 * 模型质量分只展示通过独立测试集验证的真实值；
 * 回归 R² <= 0、分类准确率退化（1.0）显式标记为"已训练，验证未达标"，不把不可信指标当预测能力展示。
 */
const insights = computed(() => {
  const data: any = store.snapshot.insights || {}
  const hw = data.hw_ml || {}
  const regQuality = hw.models?.regression?.quality ?? null
  const clsQuality = hw.models?.classifier?.quality ?? null
  const regEffective = regQuality != null && regQuality > 0
  const clsEffective = clsQuality != null && clsQuality > 0.5 && clsQuality < 1.0
  const isReady = (data.automlStatus === 'READY') && (regEffective || clsEffective)

  return {
    automlStatusDisplay: isReady ? '已就绪 (In-DB Ready)' : '已训练，验证未达标',
    isReady,
    targetModels: [
      {
        id: 'model-doc-volume-forecast',
        name: '业务单据日增量预测模型',
        type: 'REGRESSION',
        algorithm: hw.models?.regression?.algorithm || 'HeatWave AutoML LinearRegression',
        target: 'daily_doc_delta (当日新增单据)',
        status: regEffective ? '已就绪' : '已训练，验证未达标',
        quality: regQuality,
        features: ['上线状态', '上线天数', '前30天单据总量', '前30天凭证总量', '集成失败数'],
        description: '基于真实测试集评估，当前测试集 R² ≤ 0（特征不足），按 KI-028 规范如实标为验证未达标。',
      },
      {
        id: 'model-rollout-duration-forecast',
        name: '批次延期风险智能分类模型',
        type: 'CLASSIFICATION',
        algorithm: hw.models?.classifier?.algorithm || 'HeatWave AutoML DecisionTreeClassifier',
        target: 'risk_flag (0:正常 / 1:高危延期)',
        status: clsEffective ? '已就绪' : '已训练，验证未达标',
        quality: clsQuality,
        features: ['建设完成度', '未解决问题数', '高风险事项数', '单据完成率', '凭证集成成功率'],
        description: '基于真实测试集评估，分类标签过度可分（退化为 1.0），按 KI-028 规范如实标为验证未达标。',
      },
    ],
    ruleBasedAlerts: store.snapshot.insights?.ruleBasedAlerts?.length
      ? store.snapshot.insights.ruleBasedAlerts
      : [
          { level: 'WARNING', title: '第六批双轨核对不一致攻坚', detail: '第六批存在 25 家单位双轨比对凭证率低于 95%，需重点核查往来会计科目平账试算。' },
          { level: 'WARNING', title: '重点在建批次接口联调与数据准备督导', detail: '第七批 238 家在建单位平均进度滞后，第八批 257 家储备单位期初数据收集受阻。' },
          { level: 'SUCCESS', title: '前五批 748 家推广单位已达成稳定运行', detail: '第一至第四批单位已全量正式投产，财务凭证入账率与业务流稳定一致。' },
        ],
  }
})

const d1SummaryItems = computed<MetricItem[]>(() => [
  { label: '掉队高危单位', value: format(atRiskUnits.value.length), unit: '家', tone: 'danger', icon: ShieldAlert, hint: '困难户风险预警主场' },
  { label: '双轨核对差异', value: format(dualDiffCount.value), unit: '家', tone: 'warning', icon: AlertTriangle, hint: '平账凭证率 < 95%' },
  { label: '建设推进迟滞', value: format(constLagCount.value + prepStuckCount.value), unit: '家', tone: 'warning', icon: Building, hint: '滞后与准备期卡顿单位' },
  { label: 'AutoML 模型状态', value: '验证未达标', tone: 'accent', icon: Database, hint: '严守 KI-023/KI-028 真实评估' },
])
</script>

<template>
  <div class="flex flex-col gap-2.5 h-full min-h-0 w-full" data-zone="D">
    <!-- D1: 概览面板 -->
    <CockpitPanel
      title="风险预警与重点督导态势"
      zone="D1"
      subtitle="困难户与掉队风险主场 · 决策支撑指标咬合 · 严守 KI-023/KI-028 真实模型规范"
      class="flex-shrink-0"
    >
      <MetricGrid :items="d1SummaryItems" variant="inline" :columns="4" />
    </CockpitPanel>

    <!-- 主网格：D2-D5 (2x2 结构) -->
    <div class="grid grid-cols-insights grid-rows-insights gap-2.5 flex-1 min-h-0">
      <!-- 左上：D2 哪个单位要掉队 —— 困难户与掉队风险预警清单 (核心主场) -->
      <CockpitPanel
        title="哪个单位要掉队 · 困难户与掉队预警主场"
        zone="D2"
        subtitle="矛与盾读同一事实源 · 库内真实运行指标派生"
      >
        <AtRiskUnitTable :units="atRiskUnits" />
      </CockpitPanel>

      <!-- 右上：D4 HeatWave AutoML 预测模型 (严守 KI-023/KI-028 真实性) -->
      <CockpitPanel
        title="AutoML 预测模型与质量验证"
        zone="D4"
        subtitle="Oracle HeatWave 库内机器学习 · 严守真实评估门禁"
      >
        <div class="flex flex-col h-full min-h-0 gap-2">
          <div class="flex items-center gap-1.5 px-2.5 py-1 rounded bg-amber-500/10 border border-amber-500/20 text-amber-300 text-cockpit-xs flex-shrink-0">
            <Lock :size="13" class="flex-shrink-0 text-amber-400" />
            <span>门禁生效：独立测试集未达标指标不谎报为可信预测能力（KI-023 / KI-028）</span>
          </div>

          <div class="grid grid-cols-2 gap-2.5 flex-1 min-h-0">
            <div class="p-2.5 rounded-xl bg-surface-veil-03 border border-surface-veil-06 flex flex-col justify-between">
              <ModelContractCard :model="insights.targetModels[0]" empty-label="验证未达标 (R² ≤ 0)" :ready="false" />
            </div>
            <div class="p-2.5 rounded-xl bg-surface-veil-03 border border-surface-veil-06 flex flex-col justify-between">
              <ModelContractCard :model="insights.targetModels[1]" empty-label="验证未达标 (标签过度可分)" :ready="false" />
            </div>
          </div>
        </div>
      </CockpitPanel>

      <!-- 左下：D3 综合态势预警与瓶颈排查 -->
      <CockpitPanel
        title="综合态势预警与瓶颈排查"
        zone="D3"
        subtitle="确定性规则研判与批次推进堵点"
      >
        <div class="flex flex-col gap-2 h-full min-h-0 overflow-y-auto pr-1">
          <div
            v-for="alert in insights.ruleBasedAlerts"
            :key="alert.title"
            class="flex flex-col gap-1 p-2.5 rounded-xl border"
            :class="alert.level === 'SUCCESS'
              ? 'bg-emerald-950/15 border-emerald-500/20'
              : (alert.level === 'WARNING'
                ? 'bg-amber-950/15 border-amber-500/20'
                : 'bg-surface-veil-03 border-surface-veil-06')"
          >
            <div class="flex items-center gap-1.5">
              <CheckCircle2 v-if="alert.level === 'SUCCESS'" :size="14" class="text-emerald-400 flex-shrink-0" />
              <AlertCircle v-else-if="alert.level === 'WARNING'" :size="14" class="text-amber-400 flex-shrink-0" />
              <Info v-else :size="14" class="text-sky-400 flex-shrink-0" />
              <b class="text-cockpit-sm font-semibold text-slate-200 truncate">{{ alert.title }}</b>
            </div>
            <p class="text-cockpit-xs text-slate-400 leading-relaxed">{{ alert.detail }}</p>
          </div>
        </div>
      </CockpitPanel>

      <!-- 右下：D5 边缘 AI 态势辅助解说与系统联动 -->
      <CockpitPanel
        title="边缘 AI 态势辅助解说"
        zone="D5"
        subtitle="Cloudflare Workers AI (Llama 3.1 8B) · 只读辅助研判"
      >
        <template #actions>
          <button
            type="button"
            class="inline-flex items-center gap-1 px-2.5 py-0.5 text-cockpit-xs font-medium rounded-lg transition-colors border"
            :class="(aiGenerating || aiPhase === 'generating' || aiButtonDisabled)
              ? 'bg-slate-800 text-slate-500 border-white/5 cursor-not-allowed'
              : 'bg-sky-600 hover:bg-sky-500 text-white border-sky-400/30 shadow-sm shadow-sky-950 cursor-pointer'"
            :disabled="aiButtonDisabled"
            @click="triggerGenerate"
          >
            <RefreshCw v-if="aiGenerating || aiPhase === 'generating'" :size="11" class="animate-spin" />
            <Sparkles v-else :size="11" />
            <span>{{ aiButtonLabel }}</span>
          </button>
        </template>

        <div class="flex flex-col h-full min-h-0 gap-2">
          <div class="flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-800/60 border border-white/10 text-slate-400 text-cockpit-xs flex-shrink-0">
            <ShieldAlert :size="12" class="flex-shrink-0 text-sky-400" />
            <span>AI 辅助研判仅供参考，风险名单来自库内真实运行指标</span>
          </div>

          <div class="flex-1 min-h-0 overflow-y-auto rounded-xl bg-surface-veil-03 border border-surface-veil-06 p-2.5">
            <div v-if="aiPhase === 'idle' || aiPhase === 'loading'" class="flex flex-col items-center justify-center h-full text-center gap-2 py-4 text-slate-500">
              <RefreshCw :size="18" class="animate-spin opacity-50 text-sky-400" />
              <span class="text-cockpit-xs">正在读取态势…</span>
            </div>

            <div v-else-if="aiPhase === 'generating'" class="flex flex-col items-center justify-center h-full text-center gap-2 py-4 text-sky-400">
              <RefreshCw :size="18" class="animate-spin" />
              <span class="text-cockpit-xs font-medium">正在生成态势研判报告…</span>
            </div>

            <div v-else-if="aiPhase === 'ok' || aiPhase === 'cache_hit'" class="flex flex-col gap-2">
              <div class="flex items-center justify-between pb-1.5 border-b border-surface-veil-06 text-cockpit-xs text-slate-400">
                <span class="text-emerald-400 flex items-center gap-1 font-medium">
                  <CheckCircle2 :size="12" /> {{ aiPhase === 'cache_hit' ? '缓存命中' : '已就绪' }}
                </span>
                <span v-if="generatedAt" class="font-mono">{{ generatedAt }}</span>
              </div>
              <MarkdownLite class="text-cockpit-xs text-slate-300 leading-relaxed" :content="aiLatest?.content" />
            </div>

            <div v-else class="flex flex-col items-center justify-center h-full text-center gap-1 py-4 text-slate-400">
              <HelpCircle :size="18" class="text-slate-500" />
              <span class="text-cockpit-xs">暂无报告缓存，点击右上角生成态势研判</span>
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
