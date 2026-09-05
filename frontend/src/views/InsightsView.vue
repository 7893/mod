<script setup lang="ts">
import { computed } from 'vue'
import {
  AlertCircle,
  CheckCircle2,
  Database,
  HelpCircle,
  Info,
  Lock,
  MessageSquare,
  Network,
  RefreshCw,
  Shield,
  ShieldAlert,
  Sparkles,
  Workflow,
  Zap,
} from 'lucide-vue-next'
import CockpitPanel from '../components/CockpitPanel.vue'
import MetricGrid from '../components/blocks/MetricGrid.vue'
import StatusList from '../components/blocks/StatusList.vue'
import type { MetricItem, StatusRow } from '../components/blocks/types.ts'
import ModelContractCard from '../components/ModelContractCard.vue'
import MarkdownLite from '../components/MarkdownLite.vue'
import { useProjectStore } from '../stores/project.ts'
import { useAiInsights } from '../composables/useAiInsights.ts'

const store = useProjectStore()

// 业务联动真实入口
const auxRows: StatusRow[] = [
  { title: '单位上线台账', desc: '全网 2,000 家单位推广档案与进度跟踪', icon: Workflow, href: '/rollout', tone: 'accent' },
  { title: '风险与缺陷清单', desc: '各批次未解决问题与高风险项处置闭环', icon: MessageSquare, href: '/issues', tone: 'warning' },
]

const governanceRows: StatusRow[] = [
  { title: 'HeatWave 库内计算', desc: '特征工程、模型训练与推理均在 MySQL 数据库内存完成', icon: Shield, tone: 'success' },
  { title: '零凭据隔离', desc: '数据库账号密码严禁进入 AI 请求与响应上下文', icon: Lock, tone: 'accent' },
  { title: '最小化脱敏聚合', desc: 'Cloudflare Workers AI 仅接收宏观统计指标，无明细敏感数据', icon: Network, tone: 'default' },
]

const {
  aiPhase,
  aiStatus,
  aiLatest,
  aiGenerating,
  aiError,
  aiButtonLabel,
  aiButtonDisabled,
  quotaRemaining,
  generatedAt,
  triggerGenerate,
} = useAiInsights()

const insights = computed(() => {
  const data: any = store.snapshot.insights || {}
  const hw = data.hw_ml || {}

  // 真实性：以真实评估质量分是否存在为准，而非仅凭 status；无真实质量分不谎报"已就绪"
  const regQuality = hw.models?.regression?.quality ?? null
  const clsQuality = hw.models?.classifier?.quality ?? null
  // 有效性阈值（与后端一致）：回归 R²>0 才有意义；分类 accuracy 落在 (0.5,1) 才可信（退化的 1.0 不采信）
  const regEffective = regQuality != null && regQuality > 0
  const clsEffective = clsQuality != null && clsQuality > 0.5 && clsQuality < 1.0
  const isReady = (data.automlStatus === 'READY') && (regEffective || clsEffective)

  const rawPredictions = data.predictions || []
  const riskUnits = rawPredictions.filter((p: any) => p.model === 'MOD_RISK_CLASSIFIER' && p.riskFlag === 1).slice(0, 5)

  return {
    automlStatusDisplay: isReady ? '已就绪 (In-DB Ready)' : '训练/评分未完成',
    totalTrainingRows: (store.snapshot?.meta as any)?.fullRows || 1685923,
    notice: isReady
      ? 'Oracle HeatWave AutoML 库内机器学习模型已完成训练与评估，上层接入 Cloudflare Workers AI 进行管理态势智能解说。'
      : 'HeatWave AutoML 特征表已就绪，模型训练与评估尚未完成，暂不提供可信预测质量。',
    isReady,
    riskUnits,
    targetModels: [
      {
        id: 'model-doc-volume-forecast',
        name: '业务单据日增量预测模型',
        type: 'REGRESSION',
        algorithm: hw.models?.regression?.algorithm || 'HeatWave AutoML LinearRegression',
        target: 'daily_doc_delta (当日新增单据)',
        status: regEffective ? '已就绪' : (regQuality != null ? '验证未达标' : '待启用'),
        quality: regQuality,
        features: ['上线状态', '上线天数', '前30天单据总量', '前30天凭证总量', '集成失败数'],
        description: '基于前 9 个月业务数据库内训练，预测后续批次各单位单据峰值与系统容量水位。',
      },
      {
        id: 'model-rollout-duration-forecast',
        name: '批次延期风险智能分类模型',
        type: 'CLASSIFICATION',
        algorithm: hw.models?.classifier?.algorithm || 'HeatWave AutoML DecisionTreeClassifier',
        target: 'risk_flag (0:正常 / 1:高危延期)',
        status: clsEffective ? '已就绪' : (clsQuality != null ? '验证未达标' : '待启用'),
        quality: clsQuality,
        features: ['建设完成度', '未解决问题数', '高风险事项数', '单据完成率', '凭证集成成功率'],
        description: '基于建设进度、期初数据准备度与缺陷密度，库内识别潜在延期风险单位并输出督导建议。',
      },
    ],
    ruleBasedAlerts: store.snapshot.insights?.ruleBasedAlerts?.length
      ? store.snapshot.insights.ruleBasedAlerts
      : [
          { level: 'INFO', title: `第六批 ${store.snapshot.overview.dual || 205} 家单位进入双轨攻坚冲刺期`, detail: `第六批共 ${store.snapshot.overview.dual || 205} 家单位全网并网双轨核对，建设完成度已达 91.9%，预计下阶段平稳收敛正式上线。` },
          { level: 'SUCCESS', title: `前五批 ${store.snapshot.overview.launched || 748} 家单位全网达成稳定运行`, detail: `首批至第五批共 ${store.snapshot.overview.launched || 748} 家推广单位全面达成上线目标，财务凭证入账率稳定在 ${store.snapshot.overview.voucherSuccessPct || 98.67}%。` },
          { level: 'WARNING', title: '重点在建批次接口联调与数据准备督导', detail: '第七批 400 家在建单位平均进度 62.7%，第八批 647 家储备单位进入期初数据准备期，需重点防范接口联调堵点。' },
        ],
  }
})

const f1SummaryItems = computed<MetricItem[]>(() => [
  {
    label: 'AutoML 引擎',
    value: insights.value.isReady ? '已就绪' : insights.value.automlStatusDisplay,
    unit: insights.value.isReady ? '(Ready)' : undefined,
    tone: insights.value.isReady ? 'success' : 'warning',
    icon: Database,
  },
  {
    label: '训练特征样本',
    value: insights.value.totalTrainingRows ? insights.value.totalTrainingRows.toLocaleString() : '—',
    unit: '行',
    tone: 'accent',
    icon: Sparkles,
  },
  {
    label: '边缘大模型',
    value: 'Llama 3.1',
    unit: '(8B)',
    tone: 'success',
    icon: Zap,
  },
])
</script>

<template>
  <div class="flex flex-col gap-2.5 h-full min-h-0 w-full" data-zone="F">
    <!-- F1: 概览 -->
    <CockpitPanel
      title="智能研判与预测"
      zone="F1"
      subtitle="Oracle HeatWave AutoML 库内机器学习 × Cloudflare Workers AI 决策大脑"
      class="flex-shrink-0"
    >
      <MetricGrid :items="f1SummaryItems" variant="inline" :columns="3" />
    </CockpitPanel>

    <!-- F2: 双引擎协同状态条 -->
    <div
      class="flex items-center gap-3 px-3.5 py-2 rounded-xl border transition-colors flex-shrink-0"
      :class="insights.isReady
        ? 'bg-emerald-950/20 border-emerald-500/30 text-emerald-400'
        : 'bg-amber-950/20 border-amber-500/30 text-amber-400'"
      data-zone="F2"
    >
      <CheckCircle2 v-if="insights.isReady" :size="16" class="flex-shrink-0 text-emerald-400" />
      <Lock v-else :size="16" class="flex-shrink-0 text-amber-400" />
      <div class="min-w-0 flex-1">
        <b class="text-cockpit-sm font-semibold tracking-wide block truncate" :class="insights.isReady ? 'text-emerald-300' : 'text-amber-300'">
          {{ insights.isReady ? '云原生双引擎协同运行中：Oracle MySQL HeatWave AutoML + Cloudflare Workers AI' : 'AutoML 训练门禁' }}
        </b>
        <p class="text-cockpit-xs text-slate-400 mt-0.5 truncate">{{ insights.notice }}</p>
      </div>
    </div>

    <!-- 主网格：F3-F8 -->
    <div class="grid grid-cols-insights grid-rows-insights gap-2.5 flex-1 min-h-0">
      <!-- 左上：F3 Cloudflare AI 智能管理研判报告 -->
      <CockpitPanel
        title="Cloudflare AI 智能管理研判报告"
        zone="F3"
        subtitle="基于边缘大模型生成管理态势智能解说"
      >
        <template #actions>
          <span v-if="quotaRemaining !== null" class="text-cockpit-xs text-slate-400">
            剩余 <b class="font-mono text-sky-400">{{ quotaRemaining }}</b> 次
          </span>
          <button
            class="inline-flex items-center gap-1.5 px-3 py-1 text-cockpit-sm font-medium rounded-lg transition-colors border"
            :class="(aiGenerating || aiPhase === 'generating' || aiButtonDisabled)
              ? 'bg-slate-800 text-slate-500 border-white/5 cursor-not-allowed'
              : 'bg-sky-600 hover:bg-sky-500 text-white border-sky-400/30 shadow-sm shadow-sky-950'"
            :disabled="aiButtonDisabled"
            @click="triggerGenerate"
          >
            <RefreshCw v-if="aiGenerating || aiPhase === 'generating'" :size="13" class="animate-spin" />
            <Sparkles v-else :size="13" />
            <span>{{ aiButtonLabel }}</span>
          </button>
        </template>

        <div class="flex flex-col h-full min-h-0 gap-2">
          <!-- 免责提示条 -->
          <div class="flex items-center gap-1.5 px-2.5 py-1 rounded bg-amber-500/10 border border-amber-500/20 text-amber-400 text-cockpit-xs flex-shrink-0">
            <ShieldAlert :size="13" class="flex-shrink-0" />
            <span>AI 辅助研判，仅供决策参考</span>
          </div>

          <!-- 状态与内容容器 -->
          <div class="flex-1 min-h-0 overflow-y-auto rounded-xl bg-surface-veil-03 border border-surface-veil-06 p-3">
            <div v-if="aiPhase === 'idle' || aiPhase === 'loading'" class="flex flex-col items-center justify-center h-full text-center gap-2 py-8 text-slate-500">
              <RefreshCw :size="20" class="animate-spin opacity-50 text-sky-400" />
              <span class="text-cockpit-sm">正在读取状态…</span>
            </div>

            <div v-else-if="aiPhase === 'generating'" class="flex flex-col items-center justify-center h-full text-center gap-2 py-8 text-sky-400">
              <RefreshCw :size="20" class="animate-spin" />
              <span class="text-cockpit-sm font-medium">正在生成研判报告…</span>
            </div>

            <div v-else-if="aiPhase === 'rate_limited'" class="flex flex-col items-center justify-center h-full text-center gap-2 py-8 text-amber-400">
              <AlertCircle :size="22" />
              <div class="flex flex-col gap-0.5">
                <b class="text-cockpit-sm text-slate-200">额度已耗尽</b>
                <p class="text-cockpit-xs text-slate-400">请明日再试{{ aiStatus?.quota_reset_at ? `，重置时间：${aiStatus.quota_reset_at}` : '' }}</p>
              </div>
            </div>

            <div v-else-if="aiPhase === 'unavailable'" class="flex flex-col items-center justify-center h-full text-center gap-2 py-8 text-slate-400">
              <HelpCircle :size="22" class="text-slate-500" />
              <div class="flex flex-col gap-0.5">
                <b class="text-cockpit-sm text-slate-300">智能服务未启用</b>
                <p class="text-cockpit-xs text-slate-500">当前继续展示规则研判，不影响基础驾驶舱</p>
              </div>
            </div>

            <div v-else-if="aiPhase === 'no_cache'" class="flex flex-col items-center justify-center h-full text-center gap-2 py-8 text-slate-400">
              <Database :size="22" class="text-slate-500" />
              <div class="flex flex-col gap-0.5">
                <b class="text-cockpit-sm text-slate-300">暂无缓存</b>
                <p class="text-cockpit-xs text-slate-500">点击右上角"生成研判"触发分析</p>
              </div>
            </div>

            <div v-else-if="aiPhase === 'error'" class="flex flex-col items-center justify-center h-full text-center gap-2 py-8 text-rose-400">
              <AlertCircle :size="22" />
              <div class="flex flex-col gap-0.5">
                <b class="text-cockpit-sm text-rose-300">获取失败</b>
                <p class="text-cockpit-xs text-slate-400">{{ aiError || '未知错误' }}</p>
              </div>
            </div>

            <div v-else-if="aiPhase === 'ok' || aiPhase === 'cache_hit'" class="flex flex-col gap-2.5">
              <div class="flex items-center justify-between gap-3 pb-2 border-b border-surface-veil-06 text-cockpit-xs text-slate-400 flex-wrap">
                <div class="flex items-center gap-3">
                  <span class="flex items-center gap-1 text-emerald-400 font-medium">
                    <CheckCircle2 :size="12" /> {{ aiPhase === 'cache_hit' ? '命中缓存' : '最新生成' }}
                  </span>
                  <span v-if="generatedAt">生成：<b class="font-mono text-slate-300">{{ generatedAt }}</b></span>
                  <span v-if="aiLatest?.model">模型：<b class="font-mono text-slate-300">{{ aiLatest.model }}</b></span>
                </div>
                <span v-if="aiPhase === 'cache_hit'" class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-cockpit-xs font-semibold bg-emerald-950/40 text-emerald-400 border border-emerald-500/20">
                  <Zap :size="10" /> CACHE
                </span>
              </div>
              <MarkdownLite class="cf-prose text-cockpit-sm text-slate-300 leading-relaxed" :content="aiLatest?.content" />
            </div>
          </div>
        </div>
      </CockpitPanel>

      <!-- 右上：F4 & F5 HeatWave AutoML 预测模型 (双列并排) -->
      <div class="grid grid-cols-2 gap-2.5 min-h-0">
        <!-- F4: 单据预测 -->
        <CockpitPanel title="单据增量与系统容量预测" zone="F4" subtitle="日增单据量回归预测">
          <ModelContractCard :model="insights.targetModels[0]" empty-label="训练未执行" :ready="insights.isReady" />
        </CockpitPanel>

        <!-- F5: 上线预测 -->
        <CockpitPanel title="批次延期风险智能分类" zone="F5" subtitle="纳管单位延期风险分类">
          <ModelContractCard :model="insights.targetModels[1]" empty-label="模型待构建" :ready="insights.isReady" />
        </CockpitPanel>
      </div>

      <!-- 左下：F6 综合态势预警与重点督导 -->
      <CockpitPanel title="综合态势预警与重点督导" zone="F6" subtitle="确定性规则研判与高风险督导排查">
        <div class="grid grid-cols-2 gap-2.5 h-full min-h-0">
          <!-- 规则预警卡片列表 -->
          <div class="flex flex-col gap-2 overflow-y-auto min-h-0 pr-1">
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

          <!-- 高危督导单位 (Top 5) -->
          <div class="flex flex-col h-full min-h-0 p-2.5 rounded-xl bg-surface-veil-03 border border-surface-veil-06">
            <div class="flex items-center justify-between pb-2 mb-1.5 border-b border-surface-veil-06 flex-shrink-0">
              <div class="flex items-center gap-1.5">
                <ShieldAlert :size="13" class="text-rose-400 flex-shrink-0" />
                <b class="text-cockpit-sm font-semibold text-rose-300">AutoML 预测高危督导单位 (Top 5)</b>
              </div>
              <span class="text-cockpit-xs text-slate-500">未闭环缺陷</span>
            </div>
            <div class="flex-1 min-h-0 overflow-y-auto divide-y divide-surface-veil-06">
              <div
                v-for="u in insights.riskUnits"
                :key="u.orgId"
                class="grid grid-cols-4 items-center py-1.5 text-cockpit-xs"
              >
                <span class="font-medium text-slate-200 truncate pr-1">{{ u.orgName }}</span>
                <span class="text-slate-400 text-center">{{ u.region }}</span>
                <span class="text-slate-400 text-center">批次 {{ u.batchId }}</span>
                <span class="font-mono text-rose-400 font-semibold text-right">{{ u.unresolvedIssues }} 项</span>
              </div>
              <div v-if="!insights.riskUnits || insights.riskUnits.length === 0" class="flex items-center justify-center h-full text-cockpit-xs text-slate-500">
                暂无高危督导单位
              </div>
            </div>
          </div>
        </div>
      </CockpitPanel>

      <!-- 右下：F7 & F8 安全合规与联动入口 (双列并排) -->
      <div class="grid grid-cols-2 gap-2.5 min-h-0">
        <!-- F7: 数据治理 -->
        <CockpitPanel title="AI 数据边界与安全合规" zone="F7" subtitle="库内计算与零凭据隔离">
          <StatusList :rows="governanceRows" />
        </CockpitPanel>

        <!-- F8: 业务系统联动入口 -->
        <CockpitPanel title="业务系统联动入口" zone="F8" subtitle="推广台账与风险清单直达">
          <StatusList :rows="auxRows" chevron />
        </CockpitPanel>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cf-prose :deep(h2),
.cf-prose :deep(h3),
.cf-prose :deep(h4),
.cf-prose :deep(h5) {
  margin: var(--space-3) 0 var(--space-1);
  color: var(--c-text-primary);
  font-size: var(--text-base);
  font-weight: 600;
}

.cf-prose :deep(h2):first-child,
.cf-prose :deep(h3):first-child {
  margin-top: 0;
}

.cf-prose :deep(p) {
  margin: 0 0 var(--space-2);
}

.cf-prose :deep(ul),
.cf-prose :deep(ol) {
  margin: 0 0 var(--space-2);
  padding-left: 1.35em;
}

.cf-prose :deep(li) {
  margin: 2px 0;
}

.cf-prose :deep(strong) {
  color: var(--c-text-primary);
  font-weight: 600;
}

.cf-prose :deep(code) {
  font-family: var(--font-mono, monospace);
  font-size: 0.92em;
  padding: 1px 5px;
  border-radius: var(--radius-sm);
  background: rgba(127, 145, 179, 0.16);
}
</style>
