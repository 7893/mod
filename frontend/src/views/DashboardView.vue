<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowUpRight, ChevronRight } from 'lucide-vue-next'
import ChinaMap from '../components/ChinaMap.vue'
import CockpitTopBar from '../components/CockpitTopBar.vue'
import CockpitPanel from '../components/CockpitPanel.vue'
import PanelLegend from '../components/PanelLegend.vue'
import OverviewTrendChart from '../components/OverviewTrendChart.vue'
import EmptyNote from '../components/blocks/EmptyNote.vue'
import MetricGrid from '../components/blocks/MetricGrid.vue'
import StatusList from '../components/blocks/StatusList.vue'
import type { MetricItem, StatusRow } from '../components/blocks/types.ts'
import { formatCount, formatPercent } from '../formatters/metrics.ts'
import { useLiveProjection } from '../composables/useLiveProjection.ts'
import { useDailyBriefing } from '../composables/useDailyBriefing.ts'
import { useLiveProjectionStore } from '../stores/liveProjection.ts'
import { useProjectStore } from '../stores/project.ts'

const store = useProjectStore()
const liveStore = useLiveProjectionStore()
const router = useRouter()
const selectedProvince = ref('全国')
const { connected: projectionConnected, recentEvent } = useLiveProjection(liveStore.apply)

const { briefing } = useDailyBriefing()
const briefingSummary = computed(() => {
  const content = briefing.value?.content
  if (!content) return ''
  return content
    .split('\n')
    .map((line) => line.replace(/[#*`>-]/g, '').trim())
    .find((line) => line.length > 8) || ''
})

const selectedProvinceData = computed(() => {
  if (selectedProvince.value === '全国') {
    return {
      total: store.snapshot.overview.orgTotal,
      launched: store.snapshot.overview.launched,
      dual: store.snapshot.overview.dual,
      progress: store.snapshot.overview.constructionPct,
      todayAdded: store.snapshot.overview.docsTodayAdded,
    }
  }

  const item = store.provinceSummary.find((province) => province.name === selectedProvince.value)
  if (!item) return { total: 0, launched: 0, dual: 0, progress: 0, todayAdded: 0 }
  return {
    total: item.total,
    launched: item.launched,
    dual: item.dual,
    progress: item.value,
    todayAdded: item.todayAdded ?? item.docsTodayAdded ?? 0,
  }
})

const provinceFacts = computed<MetricItem[]>(() => [
  {
    label: '建设完成率',
    value: formatPercent(selectedProvinceData.value.progress),
    tone: 'accent',
    progress: selectedProvinceData.value.progress,
  },
  {
    label: '已上线',
    value: formatCount(selectedProvinceData.value.launched),
    unit: '家',
    tone: 'success',
    hint: `纳入 ${formatCount(selectedProvinceData.value.total)} 家`,
  },
  {
    label: '双轨运行',
    value: formatCount(selectedProvinceData.value.dual),
    unit: '家',
    tone: 'warning',
  },
  {
    label: '今日单据',
    value: `+${formatCount(selectedProvinceData.value.todayAdded)}`,
    tone: 'accent',
  },
])

const todayFacts = computed<MetricItem[]>(() => [
  {
    label: '今日业务单据',
    value: `+${formatCount(liveStore.liveOverview.docsTodayAdded)}`,
    tone: 'accent',
  },
  {
    label: '今日会计凭证',
    value: `+${formatCount(liveStore.liveOverview.vouchersTodayAdded)}`,
    tone: 'success',
  },
  {
    label: '实时集成推送',
    value: `+${formatCount(liveStore.cumulative.integrations)}`,
    tone: 'warning',
    hint: '当前投影会话',
  },
  {
    label: '今日新增单位',
    value: `+${formatCount(store.snapshot.overview.orgTodayAdded)}`,
    tone: 'default',
  },
])

const qualityErrorCount = computed<number | null>(() => {
  const quality = store.snapshot.quality
  const values = [quality?.voucherBalanceErrors, quality?.timeOrderErrors, quality?.orphanLinkErrors]
  return values.every((value) => value != null)
    ? values.reduce<number>((sum, value) => sum + Number(value), 0)
    : null
})

const operationalExceptions = computed(() => [
  { id: 'ops-integration', title: '接口失败待核', value: store.snapshot.operations?.integrationFailed ?? null },
  { id: 'ops-dual', title: '双轨差异待核', value: store.snapshot.operations?.dualRunInconsistent ?? null },
  { id: 'ops-quality', title: '金标异常待核', value: qualityErrorCount.value },
])

const actionRows = computed<StatusRow[]>(() => {
  const operationsRows: StatusRow[] = operationalExceptions.value
    .filter((item) => item.value == null || item.value > 0)
    .map((item) => ({
      id: item.id,
      title: item.title,
      desc: item.value == null ? '业务运行 · 数据未完整' : `业务运行 · ${formatCount(item.value)} 项待处理`,
      dot: true,
      tone: item.value == null ? 'default' : 'danger',
    }))

  const issueRows: StatusRow[] = (store.snapshot.issues || []).map((item, index) => ({
    id: `risk-${index}-${item.orgName}-${item.type}`,
    title: item.title,
    desc: `${item.area} · ${item.owner} · ${item.status}`,
    dot: true,
    tone: item.level === '高' ? 'danger' : (item.status === '正常' ? 'success' : 'warning'),
  }))

  return [...operationsRows, ...issueRows]
})

const chooseProvince = (name: string) => {
  selectedProvince.value = selectedProvince.value === name ? '全国' : name
}

const openAction = (row: StatusRow) => {
  router.push(String(row.id).startsWith('ops-') ? '/d' : '/f')
}
</script>

<template>
  <div class="w-full h-full p-3 bg-surface-base flex flex-col gap-2.5 overflow-hidden select-none">
    <header class="flex-shrink-0">
      <CockpitTopBar
        :overview="store.snapshot.overview"
        :issues-summary="store.snapshot.issuesSummary"
        :construction="store.snapshot.construction"
        :live="liveStore.liveOverview"
        :projection-connected="projectionConnected"
        :recent-event="recentEvent"
        @navigate="router.push"
      />
    </header>

    <button
      type="button"
      class="h-8 flex-shrink-0 flex items-center justify-center gap-2 px-3 rounded-lg bg-sky-500/10 border border-sky-500/20 text-center hover:bg-sky-500/15 transition-colors cursor-pointer w-full min-w-0 disabled:invisible disabled:pointer-events-none"
      :disabled="!briefingSummary"
      :title="briefingSummary ? '点击查看智能研判全文' : undefined"
      @click="router.push('/f')"
    >
      <span class="flex-shrink-0 font-mono text-cockpit-xs font-bold px-1.5 py-0.5 rounded bg-sky-500/20 text-sky-300 border border-sky-400/30">{{ briefing?.isStale ? `历史简报 ${briefing.briefingDate}` : 'AI 简报' }}</span>
      <span class="text-cockpit-sm text-slate-300 truncate min-w-0 max-w-4xl">{{ briefingSummary }}</span>
      <ChevronRight :size="13" class="flex-shrink-0 text-sky-400" />
    </button>

    <main class="flex-1 grid grid-cols-cockpit gap-2.5 min-h-0">
      <aside class="grid grid-rows-dashboard-left gap-2.5 min-h-0">
        <CockpitPanel
          title="省域摘要"
          zone="A2"
          :subtitle="selectedProvince === '全国' ? '全国总体 · 点击地图切换省域' : `${selectedProvince} · 纳入 ${selectedProvinceData.total} 家`"
        >
          <template #actions>
            <div class="flex items-center gap-1.5">
              <button
                v-if="selectedProvince !== '全国'"
                class="text-cockpit-sm font-medium text-amber-400 hover:text-amber-300 transition-colors px-2 py-0.5 rounded-lg bg-amber-500/10 border border-amber-500/20 cursor-pointer"
                @click="selectedProvince = '全国'"
              >
                返回全国
              </button>
              <button
                class="text-cockpit-sm font-medium text-sky-400 hover:text-sky-300 transition-colors flex items-center gap-1 px-2 py-0.5 rounded-lg bg-sky-500/10 border border-sky-500/20 cursor-pointer"
                @click="router.push('/c')"
              >
                推广详情 <ArrowUpRight :size="12" />
              </button>
            </div>
          </template>
          <MetricGrid :items="provinceFacts" :columns="2" fill flat size="sm" />
        </CockpitPanel>

        <CockpitPanel
          title="上线双轨走势"
          zone="A4"
          :subtitle="`7 个进度节点 · 累计上线 ${store.snapshot.overview.launched ?? 0} 家`"
        >
          <template #actions>
            <PanelLegend compact :items="[
              { label: '已上线', tone: 'accent' },
              { label: '双轨核对', tone: 'warning' },
            ]" />
          </template>
          <OverviewTrendChart class="w-full h-full min-h-0" :data="store.snapshot.trend" />
        </CockpitPanel>
      </aside>

      <section data-zone="A5" class="min-h-0 rounded-xl bg-slate-900/60 border border-white/10 backdrop-blur-md overflow-hidden p-3 flex flex-col gap-2">
        <div class="flex items-center justify-between gap-3 flex-shrink-0">
          <div class="flex items-center gap-2 min-w-0">
            <span class="font-mono text-cockpit-xs font-bold px-1.5 py-0.5 rounded bg-white/5 text-slate-400 border border-white/10 tracking-wide">A5</span>
            <span class="text-cockpit-md font-semibold text-slate-100 tracking-wide">全域推展沙盘</span>
            <span class="text-cockpit-xs text-slate-500 truncate">点击省域联动左侧摘要</span>
          </div>
          <span class="font-mono text-cockpit-sm text-sky-400 flex-shrink-0">{{ selectedProvince }}</span>
        </div>

        <div class="flex-1 w-full min-h-0">
          <ChinaMap
            :data="store.provinceSummary"
            :selected="selectedProvince"
            :live-event="recentEvent"
            @select="chooseProvince"
          />
        </div>
      </section>

      <aside class="grid grid-rows-cockpit-right gap-2.5 min-h-0">
        <CockpitPanel
          title="今日变化"
          zone="A6"
          subtitle="只呈现当日增量，不重复累计规模"
        >
          <MetricGrid :items="todayFacts" :columns="2" fill flat size="sm" />
        </CockpitPanel>

        <CockpitPanel
          title="跨域行动"
          zone="A7"
          tone="risk"
          :subtitle="`${actionRows.length} 项待处置`"
        >
          <template #actions>
            <button class="text-cockpit-sm text-rose-300 hover:text-rose-200 flex items-center gap-1 cursor-pointer" @click="router.push('/f')">
              风险中心 <ChevronRight :size="13" />
            </button>
          </template>
          <StatusList v-if="actionRows.length" :rows="actionRows" scroll chevron @select="openAction" />
          <EmptyNote v-else>当前没有跨域行动项</EmptyNote>
        </CockpitPanel>
      </aside>
    </main>
  </div>
</template>
