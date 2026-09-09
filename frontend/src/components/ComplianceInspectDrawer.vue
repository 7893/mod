<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  RotateCcw,
  Send,
  ShieldAlert,
  Sparkles,
  UserCheck,
  X,
} from 'lucide-vue-next'
import { formatPercent } from '../formatters/metrics.ts'

export interface ComplianceIssueUnit {
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

export interface GovernanceIssue {
  id: string
  unitId: number
  unitName: string
  province: string
  batchId: number
  issueType: string
  severity: string
  status: string
  owner: string | null
  title: string
  description: string | null
  aiEnriched: number
  reworkCount: number
  createdAt: string
  updatedAt: string
  resolvedAt: string | null
}

export interface TimelineEvent {
  id: number
  issueId: string
  action: string
  actor: string
  detail: string
  occurredAt: string
}

const props = defineProps<{
  unit: ComplianceIssueUnit | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'dispatched', issue: GovernanceIssue): void
}>()

const issue = ref<GovernanceIssue | null>(null)
const timeline = ref<TimelineEvent[]>([])
const loading = ref(false)
const dispatching = ref(false)
const enriching = ref(false)
const actionNotice = ref<string | null>(null)
const actionError = ref(false)
let loadSequence = 0
let loadController: AbortController | null = null

const statusSteps = [
  { key: 'DISCOVERED', label: '发现' },
  { key: 'ASSIGNED', label: '指派' },
  { key: 'IN_PROGRESS', label: '攻坚' },
  { key: 'VERIFYING', label: '核验' },
  { key: 'RESOLVED', label: '销项' },
  { key: 'CLOSED', label: '归档' },
]

const isTerminal = computed(() => issue.value?.status === 'RESOLVED' || issue.value?.status === 'CLOSED')

const currentStepIndex = computed(() => {
  if (!issue.value) return 0
  const st = issue.value.status
  const idx = statusSteps.findIndex((s) => s.key === st)
  return idx !== -1 ? idx : 2
})

async function fetchIssueAndTimeline(unitId: number) {
  const sequence = ++loadSequence
  loadController?.abort()
  const controller = new AbortController()
  loadController = controller
  loading.value = true
  issue.value = null
  timeline.value = []
  actionNotice.value = null
  actionError.value = false
  try {
    const res = await fetch(`${import.meta.env.BASE_URL}api/governance/issues?unit_id=${unitId}&page_size=1`, {
      signal: controller.signal,
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    if (sequence !== loadSequence || props.unit?.id !== unitId) return
    if (data.items && data.items.length > 0) {
      const item = data.items[0] as GovernanceIssue
      const loadedTimeline = await fetchTimeline(item.id, controller.signal)
      if (sequence !== loadSequence || props.unit?.id !== unitId) return
      issue.value = item
      timeline.value = loadedTimeline
    }
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') return
    actionError.value = true
    actionNotice.value = '治理工单读取失败，请稍后重试。'
    console.warn('Failed to load governance issue:', err)
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}

async function fetchTimeline(issueId: string, signal?: AbortSignal): Promise<TimelineEvent[]> {
  const res = await fetch(`${import.meta.env.BASE_URL}api/governance/issues/${issueId}/timeline`, { signal })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return await res.json() as TimelineEvent[]
}

async function handleDispatch() {
  if (!issue.value) return
  dispatching.value = true
  actionNotice.value = null
  actionError.value = false
  const issueId = issue.value.id
  const unitId = props.unit?.id
  try {
    const res = await fetch(`${import.meta.env.BASE_URL}api/governance/issues/${issueId}/dispatch`, {
      method: 'POST',
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const updated = await res.json() as GovernanceIssue
    if (props.unit?.id !== unitId || issue.value?.id !== issueId) return
    issue.value = updated
    try {
      timeline.value = await fetchTimeline(updated.id)
      actionNotice.value = '特派军令状已下达！攻坚专班进入强力处置。'
    } catch (timelineError) {
      actionError.value = true
      actionNotice.value = '督办已成功，但时间线刷新失败，请稍后重新打开。'
      console.warn('Timeline refresh after dispatch failed:', timelineError)
    }
    emit('dispatched', updated)
  } catch (err) {
    actionError.value = true
    actionNotice.value = '督办失败，工单未变更，请稍后重试。'
    console.warn('Dispatch failed:', err)
  } finally {
    dispatching.value = false
  }
}

async function handleEnrich() {
  if (!issue.value) return
  enriching.value = true
  actionNotice.value = null
  actionError.value = false
  const issueId = issue.value.id
  const unitId = props.unit?.id
  try {
    const res = await fetch(`${import.meta.env.BASE_URL}api/governance/issues/${issueId}/enrich`, {
      method: 'POST',
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const updated = await res.json() as GovernanceIssue
    if (props.unit?.id !== unitId || issue.value?.id !== issueId) return
    issue.value = updated
    try {
      timeline.value = await fetchTimeline(updated.id)
      actionNotice.value = 'AI 专家研判完成，已回填深层根因与销项举措。'
    } catch (timelineError) {
      actionError.value = true
      actionNotice.value = 'AI 研判已完成，但时间线刷新失败，请稍后重新打开。'
      console.warn('Timeline refresh after enrichment failed:', timelineError)
    }
  } catch (err) {
    actionError.value = true
    actionNotice.value = 'AI 研判失败，工单未变更，请稍后重试。'
    console.warn('Enrich failed:', err)
  } finally {
    enriching.value = false
  }
}

watch(
  () => props.unit,
  (newUnit) => {
    if (newUnit) {
      void fetchIssueAndTimeline(newUnit.id)
    } else {
      loadSequence += 1
      loadController?.abort()
      issue.value = null
      timeline.value = []
      actionNotice.value = null
    }
  },
  { immediate: true },
)
</script>

<template>
  <div v-if="unit" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex justify-end" @click.self="emit('close')">
    <aside class="w-96 h-full bg-slate-900 border-l border-white/10 p-5 flex flex-col gap-3.5 shadow-2xl overflow-y-auto">
      <!-- 头部 -->
      <header class="flex items-center justify-between border-b border-white/5 pb-3">
        <div>
          <div class="flex items-center gap-1.5">
            <span class="font-mono text-cockpit-xs text-sky-400 font-bold">MOD-{{ unit.id }}</span>
            <span v-if="issue" class="font-mono text-cockpit-xs text-slate-500 font-semibold">{{ issue.id }}</span>
          </div>
          <h3 class="text-cockpit-md font-semibold text-slate-100">合规攻防与督办协同</h3>
        </div>
        <button
          type="button"
          class="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-colors cursor-pointer"
          @click="emit('close')"
        >
          <X :size="18" />
        </button>
      </header>

      <!-- 单位卡片 -->
      <div class="p-3 rounded-lg bg-surface-veil-03 border border-surface-veil-06 flex flex-col gap-1">
        <div class="flex items-center justify-between">
          <b class="text-cockpit-md font-semibold text-slate-100 truncate">{{ unit.name }}</b>
          <span
            v-if="issue"
            class="px-1.5 py-0.5 rounded text-cockpit-xs font-semibold"
            :class="isTerminal ? 'text-emerald-400 bg-emerald-950/40' : 'text-amber-400 bg-amber-950/40'"
          >
            {{ isTerminal ? '已闭环归档' : '攻坚治理中' }}
          </span>
        </div>
        <span class="text-cockpit-sm text-slate-400">{{ unit.province }} · {{ unit.batch }} · 经办人：{{ unit.owner }}</span>
      </div>

      <!-- 治理状态机六态步进指示器 -->
      <div v-if="issue" class="p-2.5 rounded-lg bg-surface-veil-03 border border-surface-veil-06 flex flex-col gap-2">
        <div class="flex items-center justify-between text-cockpit-xs">
          <span class="font-medium text-slate-300">治理推进状态机 (The Shield)</span>
          <span v-if="issue.reworkCount > 0" class="inline-flex items-center gap-1 text-rose-400 font-semibold">
            <RotateCcw :size="10" />
            二次返工 x{{ issue.reworkCount }}
          </span>
        </div>
        <div class="grid grid-cols-6 gap-1 text-center font-mono text-cockpit-xs">
          <div
            v-for="(st, idx) in statusSteps"
            :key="st.key"
            class="py-1 rounded border transition-colors"
            :class="idx <= currentStepIndex
              ? (idx === currentStepIndex
                ? 'bg-sky-500/20 border-sky-500/40 text-sky-300 font-bold'
                : 'bg-emerald-950/30 border-emerald-500/30 text-emerald-400')
              : 'bg-surface-veil-03 border-surface-veil-06 text-slate-600'"
          >
            {{ st.label }}
          </div>
        </div>
        <div class="flex items-center justify-between text-cockpit-xs text-slate-400 pt-1 border-t border-surface-veil-06">
          <span class="flex items-center gap-1">
            <UserCheck :size="11" class="text-sky-400" />
            专班专员：{{ issue.owner || '指挥中心调度中' }}
          </span>
          <span class="font-mono text-slate-500">状态以工单流水为准</span>
        </div>
      </div>

      <!-- 上帝之手双向督办动作条 -->
      <div v-if="issue && !isTerminal" class="flex items-center gap-2">
        <button
          type="button"
          :disabled="dispatching"
          class="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white font-semibold transition-colors text-cockpit-xs cursor-pointer shadow-lg shadow-sky-950/40"
          @click="handleDispatch"
        >
          <Send :size="12" :class="{ 'animate-pulse': dispatching }" />
          <span>{{ dispatching ? '特派指令下达中…' : '一键督办（指挥部令）' }}</span>
        </button>

        <button
          type="button"
          :disabled="enriching"
          class="flex items-center justify-center gap-1 px-3 py-1.5 rounded-lg bg-surface-veil-03 hover:bg-white/10 border border-surface-veil-06 disabled:opacity-50 text-slate-200 font-medium transition-colors text-cockpit-xs cursor-pointer"
          title="调用 Cloudflare Workers AI 深度研判（受 3,000 Neurons/日 硬限制保护，保障 $0.00 账单）"
          @click="handleEnrich"
        >
          <Sparkles :size="12" class="text-amber-400" :class="{ 'animate-spin': enriching }" />
          <span>{{ enriching ? 'AI研判中…' : 'AI深度研判' }}</span>
        </button>
      </div>

      <!-- 操作通知反馈 -->
      <div
        v-if="actionNotice"
        class="p-2 rounded text-cockpit-xs flex items-center gap-1.5"
        :class="actionError ? 'bg-rose-950/30 border border-rose-500/30 text-rose-400' : 'bg-emerald-950/30 border border-emerald-500/30 text-emerald-400'"
      >
        <AlertTriangle v-if="actionError" :size="13" class="flex-shrink-0" />
        <CheckCircle2 v-else :size="13" class="flex-shrink-0" />
        <span>{{ actionNotice }}</span>
      </div>

      <!-- 专家深入研判内容 -->
      <div v-if="issue && issue.description" class="flex flex-col gap-1.5">
        <span class="text-cockpit-sm font-semibold text-slate-300">工单叙事与研判</span>
        <div class="text-cockpit-xs text-slate-300 bg-surface-veil-03 p-3 rounded-lg border border-surface-veil-06 leading-relaxed max-h-40 overflow-y-auto whitespace-pre-wrap">
          {{ issue.description }}
        </div>
      </div>

      <!-- 全生命周期流转时间线 -->
      <div class="flex flex-col gap-2 flex-1 min-h-0">
        <div class="flex items-center justify-between">
          <span class="text-cockpit-sm font-semibold text-slate-300">全生命周期治理流水</span>
          <span class="font-mono text-cockpit-xs text-slate-500">{{ timeline.length }} 个关键节点</span>
        </div>

        <div v-if="timeline.length > 0" class="flex flex-col gap-2 overflow-y-auto pr-1">
          <div
            v-for="ev in timeline"
            :key="ev.id"
            class="p-2 rounded-lg bg-surface-veil-03 border border-surface-veil-06 flex flex-col gap-1 text-cockpit-xs"
          >
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-1.5">
                <span
                  class="px-1.5 py-0.5 rounded font-medium"
                  :class="ev.action === '一键督办'
                    ? 'bg-rose-950/40 text-rose-400 border border-rose-500/30'
                    : (ev.action.includes('AI')
                      ? 'bg-sky-950/40 text-sky-400 border border-sky-500/30'
                      : (ev.action.includes('销项')
                        ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-500/30'
                        : 'bg-slate-800 text-slate-300'))"
                >
                  {{ ev.action }}
                </span>
                <span class="text-slate-300 font-medium truncate">{{ ev.actor }}</span>
              </div>
              <span class="font-mono text-slate-500 text-cockpit-xs">{{ ev.occurredAt }}</span>
            </div>
            <p class="text-slate-400 leading-normal">{{ ev.detail }}</p>
          </div>
        </div>

        <div v-else class="text-center py-4 text-slate-500 text-cockpit-xs">
          {{ loading ? '正在读取时间线流水…' : '暂无流转记录' }}
        </div>
      </div>

      <!-- 底座指标核验 -->
      <div class="flex flex-col gap-1.5 pt-2 border-t border-white/5">
        <div class="grid grid-cols-4 gap-1.5 text-cockpit-xs text-center">
          <div class="p-1.5 rounded bg-surface-veil-03 border border-surface-veil-06">
            <span class="text-slate-500 block">建设</span>
            <b class="font-mono text-sky-400">{{ unit.construction }}%</b>
          </div>
          <div class="p-1.5 rounded bg-surface-veil-03 border border-surface-veil-06">
            <span class="text-slate-500 block">期初</span>
            <b class="font-mono text-amber-400">{{ unit.openingData }}%</b>
          </div>
          <div class="p-1.5 rounded bg-surface-veil-03 border border-surface-veil-06">
            <span class="text-slate-500 block">状态</span>
            <b class="text-slate-300 truncate block">{{ unit.status }}</b>
          </div>
          <div class="p-1.5 rounded bg-surface-veil-03 border border-surface-veil-06">
            <span class="text-slate-500 block">双轨</span>
            <b class="font-mono text-emerald-400">{{ formatPercent(unit.voucherRate) }}</b>
          </div>
        </div>
      </div>
    </aside>
  </div>
</template>
