<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { ChevronRight } from 'lucide-vue-next'
import AnimatedNumber from './AnimatedNumber.vue'
import ChartCanvas from './charts/ChartCanvas.vue'
import CockpitPanel from './CockpitPanel.vue'
import LiveProjectionIndicator from './LiveProjectionIndicator.vue'
import {
  createOperationsVolumeOption,
  createProgressRingsOption,
  createRiskClosureOption,
} from '../charts/cockpitTopBarOptions.ts'
import { formatCount } from '../formatters/metrics.ts'
import type { LiveProjectionCounts, LiveProjectionEvent } from '../composables/useLiveProjection.ts'
import type { ProjectSnapshot } from '../stores/project.ts'

use([CanvasRenderer, BarChart, PieChart, GridComponent, TooltipComponent])

/**
 * A1 顶部总览带：双环展示建设/上线水位，规模谱展示运营总量，风险环展示闭环压力。
 */
const props = defineProps<{
  overview: ProjectSnapshot['overview']
  issuesSummary?: ProjectSnapshot['issuesSummary']
  construction?: ProjectSnapshot['construction']
  operations?: ProjectSnapshot['operations']
  live: ProjectSnapshot['overview']
  cumulative: LiveProjectionCounts
  projectionConnected: boolean
  recentEvent: LiveProjectionEvent | null
  /** 首屏之后动效时长归零，避免大屏长期展示时反复播放入场动画 */
  numDuration: (ms: number) => number
}>()

defineEmits<{ openRisk: [] }>()

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

const progressRingsOption = computed(() => createProgressRingsOption({
  constructionProgress: constructionProgress.value,
  rolloutRate: rolloutRate.value,
}))

const operationsVolumeOption = computed(() => createOperationsVolumeOption({
  documents: safeNumber(props.live.docsTotal || props.overview.docsTotal),
  vouchers: safeNumber(props.live.vouchersTotal || props.overview.vouchersTotal),
  integrations: safeNumber(props.operations?.integrationResult),
}))

const closeRate = computed(() => Math.max(0, Math.min(100, safeNumber(props.issuesSummary?.closeRate))))

const riskClosureOption = computed(() => createRiskClosureOption({
  resolved: safeNumber(props.issuesSummary?.totalResolved),
  unresolved: safeNumber(props.issuesSummary?.totalUnresolved),
}))
</script>

<template>
  <CockpitPanel
    title="全域建设运行总览"
    zone="A1"
    subtitle="34 省级行政区 · 8 批次 · 建设、推广与风险同屏"
  >
    <template #actions>
      <div class="flex items-center gap-2 text-cockpit-xs text-slate-500">
        <span class="text-emerald-400 font-mono">实时链路</span>
        <LiveProjectionIndicator :connected="projectionConnected" :event="recentEvent" />
      </div>
    </template>

    <div class="grid grid-cols-12 gap-3 h-24 min-h-[96px] max-h-[96px] overflow-hidden">
      <section class="col-span-4 grid grid-cols-5 gap-2 min-w-0 pr-3 border-r border-surface-veil-06 overflow-hidden">
        <ChartCanvas class="col-span-2" :option="progressRingsOption" />
        <div class="col-span-3 grid grid-rows-3 divide-y divide-surface-veil-06 min-w-0">
          <div class="flex items-center justify-between gap-2 text-cockpit-xs"><span class="text-slate-500">建设完成率</span><b class="font-mono text-sky-400"><AnimatedNumber :value="constructionProgress" :decimals="1" :duration="numDuration(800)" />%</b></div>
          <div class="flex items-center justify-between gap-2 text-cockpit-xs"><span class="text-slate-500">上线率</span><b class="font-mono text-emerald-400">{{ rolloutRate }}%</b></div>
          <div class="flex items-center justify-between gap-2 text-cockpit-xs"><span class="text-slate-500">建设任务</span><b class="font-mono text-slate-200">{{ formatCount(construction?.totalTasks || 0) }}</b></div>
        </div>
      </section>

      <section class="col-span-5 flex flex-col min-w-0 pr-3 border-r border-surface-veil-06 overflow-hidden">
        <div class="grid grid-cols-3 gap-2 flex-shrink-0">
          <div><span class="block text-cockpit-xs text-slate-500">今日单据</span><b class="font-mono text-cockpit-md text-emerald-400">+<AnimatedNumber :value="live.docsTodayAdded || 0" :duration="500" /></b></div>
          <div><span class="block text-cockpit-xs text-slate-500">今日凭证</span><b class="font-mono text-cockpit-md text-emerald-400">+<AnimatedNumber :value="live.vouchersTodayAdded || 0" :duration="500" /></b></div>
          <div><span class="block text-cockpit-xs text-slate-500" title="演示投影会话累计实时集成推送数">实时集成脉搏</span><b class="font-mono text-cockpit-md text-sky-400">+<AnimatedNumber :value="cumulative.integrations || 0" :duration="500" /></b></div>
        </div>
        <ChartCanvas class="flex-1" :option="operationsVolumeOption" />
      </section>

      <button
        type="button"
        class="col-span-3 flex items-center min-w-0 rounded-lg px-2 hover:bg-rose-500/10 transition-colors cursor-pointer text-left overflow-hidden"
        title="进入风险中心"
        @click="$emit('openRisk')"
      >
        <div class="h-full w-20 flex-shrink-0">
          <ChartCanvas :option="riskClosureOption" />
        </div>
        <div class="flex-1 min-w-0 grid grid-cols-3 gap-2">
          <div class="min-w-0"><span class="block text-cockpit-xs text-slate-500 truncate">闭环率</span><b class="font-mono text-cockpit-lg text-emerald-400">{{ closeRate }}%</b></div>
          <div class="min-w-0"><span class="block text-cockpit-xs text-slate-500 truncate">高风险</span><b class="font-mono text-cockpit-lg text-rose-400"><AnimatedNumber :value="overview.highRisk || 0" :duration="numDuration(600)" /></b></div>
          <div class="min-w-0"><span class="block text-cockpit-xs text-slate-500 truncate">未解决</span><b class="font-mono text-cockpit-lg text-amber-400">{{ formatCount(overview.unresolvedIssues || 0) }}</b></div>
        </div>
        <ChevronRight :size="14" class="text-slate-500 mr-2 flex-shrink-0" />
      </button>
    </div>
  </CockpitPanel>
</template>
