<script setup lang="ts">
import { computed } from 'vue'
import CockpitPanel from './CockpitPanel.vue'
import LiveProjectionIndicator from './LiveProjectionIndicator.vue'
import { formatCount, formatPercent } from '../formatters/metrics.ts'
import type { LiveProjectionEvent } from '../composables/useLiveProjection.ts'
import type { ProjectSnapshot } from '../stores/project.ts'

/**
 * A1 是五个专业屏的导航摘要，不再承载专业屏中的累计图表。
 * 每个领域只保留一个核心状态和一个解释性事实，点击进入唯一事实页。
 */
const props = defineProps<{
  overview: ProjectSnapshot['overview']
  issuesSummary?: ProjectSnapshot['issuesSummary']
  construction?: ProjectSnapshot['construction']
  projectionConnected: boolean
  recentEvent: LiveProjectionEvent | null
}>()

const emit = defineEmits<{ navigate: [path: string] }>()

const safeNumber = (value?: number | null) => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

const constructionProgress = computed(() => Math.max(0, Math.min(100, safeNumber(props.overview.constructionPct))))
const rolloutRate = computed(() => {
  const total = safeNumber(props.overview.orgTotal)
  const launched = safeNumber(props.overview.launched)
  return total > 0 ? Math.round((launched * 1000) / total) / 10 : 0
})
const closeRate = computed(() => Math.max(0, Math.min(100, safeNumber(props.issuesSummary?.closeRate))))

type DomainTone = 'accent' | 'success' | 'warning' | 'danger'

interface DomainCard {
  id: string
  label: string
  value: string
  detail: string
  route: string
  tone: DomainTone
}

const domainCards = computed<DomainCard[]>(() => [
  {
    id: 'B',
    label: '工程建设',
    value: formatPercent(constructionProgress.value),
    detail: `${formatCount(props.construction?.totalTasks)} 项任务`,
    route: '/b',
    tone: 'accent',
  },
  {
    id: 'C',
    label: '推广上线',
    value: formatPercent(rolloutRate.value),
    detail: `${formatCount(props.overview.launched)} / ${formatCount(props.overview.orgTotal)} 家`,
    route: '/c',
    tone: 'success',
  },
  {
    id: 'D',
    label: '业务运行',
    value: formatPercent(props.overview.integrationSuccessPct),
    detail: '单据凭证全链路',
    route: '/d',
    tone: 'accent',
  },
  {
    id: 'E',
    label: '合规监督',
    value: formatPercent(closeRate.value),
    detail: `${formatCount(props.overview.unresolvedIssues)} 项待闭环`,
    route: '/e',
    tone: 'warning',
  },
  {
    id: 'F',
    label: '风险研判',
    value: formatCount(props.overview.highRisk),
    detail: '高风险单位',
    route: '/f',
    tone: 'danger',
  },
])

const valueClass: Record<DomainTone, string> = {
  accent: 'text-sky-400',
  success: 'text-emerald-400',
  warning: 'text-amber-400',
  danger: 'text-rose-400',
}
</script>

<template>
  <CockpitPanel
    title="五域指挥入口"
    zone="A1"
    subtitle="总览只回答状态与去向，专业事实进入对应业务屏"
  >
    <template #actions>
      <div class="flex items-center gap-2 text-cockpit-xs text-slate-500">
        <span class="text-emerald-400 font-mono">实时链路</span>
        <LiveProjectionIndicator :connected="projectionConnected" :event="recentEvent" />
      </div>
    </template>

    <div class="grid grid-cols-5 h-20 divide-x divide-surface-veil-06 overflow-hidden">
      <button
        v-for="card in domainCards"
        :key="card.id"
        type="button"
        class="group flex flex-col items-center justify-center gap-1 px-3 min-w-0 text-center hover:bg-white/5 transition-colors cursor-pointer"
        :title="`进入 ${card.label}`"
        @click="emit('navigate', card.route)"
      >
        <span class="flex items-center justify-center gap-2 min-w-0 w-full">
          <span class="flex-shrink-0 font-mono text-cockpit-sm font-bold text-slate-500">{{ card.id }}</span>
          <span class="text-cockpit-sm font-medium text-slate-300 truncate">{{ card.label }}</span>
        </span>
        <b class="font-mono text-cockpit-kpi leading-tight" :class="valueClass[card.tone]">{{ card.value }}</b>
        <span class="text-cockpit-xs text-slate-500 truncate w-full">{{ card.detail }}</span>
      </button>
    </div>
  </CockpitPanel>
</template>
