<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent } from 'echarts/components'
import { ChevronRight } from 'lucide-vue-next'
import AnimatedNumber from './AnimatedNumber.vue'
import CockpitPanel from './CockpitPanel.vue'
import LiveProjectionIndicator from './LiveProjectionIndicator.vue'
import CompositionBar from './blocks/CompositionBar.vue'
import { buildOverviewComposition } from '../charts/panelData.ts'
import { calmAnimation, chartInk, chartPalette, chartTooltip } from '../charts/theme.ts'
import type { LiveProjectionCounts, LiveProjectionEvent } from '../composables/useLiveProjection.ts'
import type { ProjectSnapshot } from '../stores/project.ts'

use([CanvasRenderer, PieChart, TitleComponent, TooltipComponent])

/**
 * A1 顶部总览带：建设进度与推广构成、今日实时增量、风险闭环三组信息同屏。
 * 数字用于精确读数，堆叠条与环图分别负责状态构成和闭环关系。
 */
const props = defineProps<{
  overview: ProjectSnapshot['overview']
  meta: ProjectSnapshot['meta']
  issuesSummary?: ProjectSnapshot['issuesSummary']
  construction?: ProjectSnapshot['construction']
  live: ProjectSnapshot['overview']
  cumulative: LiveProjectionCounts
  projectionConnected: boolean
  recentEvent: LiveProjectionEvent | null
  /** 首屏之后动效时长归零，避免大屏长期展示时反复播放入场动画 */
  numDuration: (ms: number) => number
  shortDate: (value?: string) => string
}>()

defineEmits<{ openRisk: [] }>()

const eventActionText = computed(() => {
  const ev = props.recentEvent as any
  if (!ev) return ''
  if (ev.story_desc) {
    const amt = ev.amount ? ` · ${ev.amount}` : ''
    return `${ev.story_desc}${amt}`
  }
  const bType = ev.business_type
  if (bType === 'org_pooled') return '新设单位登记，纳入第八批储备池'
  if (bType === 'training_certified') return '关键用户通过机房实操上岗认证考试'
  if (bType === 'dual_run_verified') return '完成 1 笔新老系统凭证借贷比对（一致）'
  if (ev.increments.vouchers > 0) return `新增会计凭证 +${ev.increments.vouchers} 张`
  if (ev.increments.documents > 0) return `新增业务单据 +${ev.increments.documents} 笔`
  if (ev.increments.integrations > 0) return `完成接口集成 +${ev.increments.integrations} 笔`
  return '业务处理中'
})

const safeNumber = (value?: number | null) => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

const constructionProgress = computed(() => Math.max(0, Math.min(100, safeNumber(props.overview.constructionPct))))

const rolloutComposition = computed(() => {
  const total = safeNumber(props.overview.orgTotal)
  const launched = safeNumber(props.overview.launched)
  const dual = safeNumber(props.overview.dual)
  return buildOverviewComposition(total, [
    { label: '已上线', value: launched, tone: 'success' },
    { label: '双轨', value: dual, tone: 'warning' },
    { label: '待推进', value: Math.max(0, total - launched - dual), tone: 'neutral' },
  ])
})

const closeRate = computed(() => Math.max(0, Math.min(100, safeNumber(props.issuesSummary?.closeRate))))

const riskClosureOption = computed(() => ({
  ...calmAnimation,
  tooltip: { trigger: 'item', ...chartTooltip },
  title: {
    text: `${closeRate.value}%`,
    subtext: '闭环率',
    left: 'center',
    top: '29%',
    textStyle: { color: chartInk.textPrimary, fontSize: 15, fontFamily: 'monospace' },
    subtextStyle: { color: chartInk.textMuted, fontSize: 9 },
  },
  series: [{
    name: '问题闭环',
    type: 'pie',
    radius: ['60%', '80%'],
    center: ['50%', '50%'],
    label: { show: false },
    data: [
      { value: safeNumber(props.issuesSummary?.totalResolved), name: '已闭环', itemStyle: { color: chartPalette.success } },
      { value: safeNumber(props.issuesSummary?.totalUnresolved), name: '未解决', itemStyle: { color: chartPalette.danger } },
    ],
  }],
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

    <div class="grid grid-cols-12 gap-3 h-20 min-h-0">
      <section class="col-span-5 flex items-stretch gap-3 min-w-0">
        <div class="w-28 flex-shrink-0 flex flex-col justify-center border-r border-surface-veil-06 pr-3">
          <span class="text-cockpit-xs text-slate-500">全网建设进度</span>
          <div class="flex items-baseline gap-1 mt-1">
            <b class="font-mono text-cockpit-metric text-sky-400"><AnimatedNumber :value="constructionProgress" :decimals="1" :duration="numDuration(800)" /></b>
            <small class="text-cockpit-xs text-slate-500">%</small>
          </div>
          <div class="h-1.5 mt-2 rounded-full bg-white/5 overflow-hidden">
            <div class="h-full rounded-full bg-sky-400" :style="{ width: `${constructionProgress}%` }" />
          </div>
          <span class="text-cockpit-xs text-slate-500 mt-1">{{ (construction?.totalTasks || 0).toLocaleString() }} 项任务</span>
        </div>

        <div class="flex-1 min-w-0 flex flex-col justify-center gap-1.5">
          <div class="grid grid-cols-3 gap-2">
            <div class="min-w-0"><span class="block text-cockpit-xs text-slate-500">业务单据</span><b class="font-mono text-cockpit-md text-slate-100"><AnimatedNumber :value="live.docsTotal || overview.docsTotal || 0" :duration="700" /></b></div>
            <div class="min-w-0"><span class="block text-cockpit-xs text-slate-500">会计凭证</span><b class="font-mono text-cockpit-md text-slate-100"><AnimatedNumber :value="live.vouchersTotal || overview.vouchersTotal || 0" :duration="700" /></b></div>
            <div class="min-w-0"><span class="block text-cockpit-xs text-slate-500">数据规模</span><b class="font-mono text-cockpit-md text-amber-400"><AnimatedNumber :value="Number(((meta?.fullRows || 0) / 10000).toFixed(1))" :decimals="1" :duration="numDuration(800)" /><small class="text-cockpit-xs text-slate-500 ml-0.5">万行</small></b></div>
          </div>
          <CompositionBar :total="rolloutComposition.total" :parts="rolloutComposition.parts" />
        </div>
      </section>

      <section class="col-span-4 flex flex-col justify-center gap-2 px-3 border-x border-surface-veil-06 min-w-0">
        <div class="grid grid-cols-3 gap-2">
          <div><span class="block text-cockpit-xs text-slate-500">今日单据</span><b class="font-mono text-cockpit-md text-emerald-400">+<AnimatedNumber :value="live.docsTodayAdded || 0" :duration="500" /></b></div>
          <div><span class="block text-cockpit-xs text-slate-500">今日凭证</span><b class="font-mono text-cockpit-md text-emerald-400">+<AnimatedNumber :value="live.vouchersTodayAdded || 0" :duration="500" /></b></div>
          <div><span class="block text-cockpit-xs text-slate-500">本次集成</span><b class="font-mono text-cockpit-md text-emerald-400">+<AnimatedNumber :value="cumulative.integrations || 0" :duration="500" /></b></div>
        </div>
        <div class="flex items-center gap-1.5 px-2 py-1 rounded bg-sky-500/10 border border-sky-500/20 text-cockpit-xs min-w-0">
          <span class="w-1.5 h-1.5 rounded-full bg-sky-400 flex-shrink-0" />
          <template v-if="recentEvent && (recentEvent.unitName || recentEvent.province)">
            <span class="text-sky-400 flex-shrink-0">[{{ recentEvent.province }}]</span>
            <span class="text-slate-200 truncate">{{ recentEvent.unitName }}</span>
            <span class="text-emerald-400 truncate ml-auto">{{ eventActionText }}</span>
          </template>
          <span v-else class="text-slate-500 truncate">实时流水线持续监听中 · {{ shortDate(live.docsAddedAsOfDate) }}</span>
        </div>
      </section>

      <button
        type="button"
        class="col-span-3 flex items-center min-w-0 rounded-lg bg-rose-950/20 border border-rose-500/20 hover:bg-rose-500/10 transition-colors cursor-pointer text-left"
        title="进入风险中心"
        @click="$emit('openRisk')"
      >
        <div class="h-full w-24 flex-shrink-0">
          <VChart :option="riskClosureOption" autoresize class="h-full w-full" />
        </div>
        <div class="flex-1 min-w-0 grid grid-cols-2 gap-2 pr-2">
          <div><span class="block text-cockpit-xs text-slate-500">高风险</span><b class="font-mono text-cockpit-lg text-rose-400"><AnimatedNumber :value="overview.highRisk || 0" :duration="numDuration(600)" /></b></div>
          <div><span class="block text-cockpit-xs text-slate-500">未解决</span><b class="font-mono text-cockpit-lg text-amber-400">{{ (overview.unresolvedIssues || 0).toLocaleString() }}</b></div>
          <span class="col-span-2 text-cockpit-xs text-slate-500 truncate">风险预警与闭环处置</span>
        </div>
        <ChevronRight :size="14" class="text-slate-500 mr-2 flex-shrink-0" />
      </button>
    </div>
  </CockpitPanel>
</template>
