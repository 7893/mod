<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, GaugeChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import {
  ChevronRight,
  ArrowUpRight,
} from 'lucide-vue-next'
import ChinaMap from '../components/ChinaMap.vue'
import CockpitTopBar from '../components/CockpitTopBar.vue'
import CockpitPanel from '../components/CockpitPanel.vue'
import PanelLegend from '../components/PanelLegend.vue'
import OverviewTrendChart from '../components/OverviewTrendChart.vue'
import StatusList from '../components/blocks/StatusList.vue'
import type { StatusRow } from '../components/blocks/types.ts'
import { buildBatchOverviewSeries, parsePercentage } from '../charts/panelData.ts'
import {
  createBatchProgressOption,
  createOperationalGuardOption,
  createOperationsQualityOption,
  createProvinceProfileOption,
} from '../charts/panelOptions.ts'
import { useLiveProjection } from '../composables/useLiveProjection.ts'
import { useDailyBriefing } from '../composables/useDailyBriefing.ts'
import { useLiveProjectionStore } from '../stores/liveProjection.ts'
import { useProjectStore } from '../stores/project.ts'

use([CanvasRenderer, BarChart, GaugeChart, GridComponent, LegendComponent, TooltipComponent])

const store = useProjectStore()
const liveStore = useLiveProjectionStore()
const router = useRouter()
const selectedProvince = ref('全国')
const { connected: projectionConnected, recentEvent } = useLiveProjection(liveStore.apply)

// 每日指挥部决策简报（后台 LLM 生成，打开即见，不交互）
const { briefing } = useDailyBriefing()
// 取简报正文首段纯文本作一行摘要（去 markdown 符号）
const briefingSummary = computed(() => {
  const c = briefing.value?.content
  if (!c) return ''
  const firstMeaningful = c
    .split('\n')
    .map((l) => l.replace(/[#*`>-]/g, '').trim())
    .find((l) => l.length > 8)
  return firstMeaningful || ''
})

// 首屏动效只播放一次：进入页面后关闭数字/进度条的强动效时长，
// 避免省份切换、数据轮询刷新时反复"跳数字+飞入"造成视觉噪音。
const isFirstLoad = ref(true)
onMounted(() => {
  window.setTimeout(() => { isFirstLoad.value = false }, 1200)
})
const numDuration = (ms: number) => (isFirstLoad.value ? ms : 0)

const selectedProvinceData = computed(() => {
  if (selectedProvince.value === '全国') {
    return {
      total: store.snapshot.overview.orgTotal,
      launched: store.snapshot.overview.launched,
      dual: store.snapshot.overview.dual,
      progress: store.snapshot.overview.constructionPct,
      todayAdded: store.snapshot.overview.docsTodayAdded,
      asOfDate: store.snapshot.overview.docsAddedAsOfDate || store.snapshot.meta.asOfDate,
    }
  }
  const item = store.provinceSummary.find((p) => p.name === selectedProvince.value)
  if (!item) {
    return { total: 0, launched: 0, dual: 0, progress: 0, todayAdded: 0, asOfDate: store.snapshot.meta.asOfDate }
  }
  return {
    total: item.total,
    launched: item.launched,
    dual: item.dual,
    progress: item.value,
    todayAdded: item.todayAdded ?? item.docsTodayAdded ?? 0,
    asOfDate: item.docsAddedAsOfDate || store.snapshot.meta.asOfDate,
  }
})

const provinceProfileOption = computed(() => createProvinceProfileOption(selectedProvinceData.value.progress))
const batchProgressOption = computed(() => createBatchProgressOption(
  buildBatchOverviewSeries(store.snapshot.rollout || []),
))

const operationsQualityOption = computed(() => createOperationsQualityOption([
  {
    name: '凭证入账',
    value: parsePercentage(store.snapshot.overview.voucherSuccessPct),
    detail: `${store.snapshot.overview.voucherTotal?.toLocaleString() ?? '—'} 张`,
    tone: 'success',
  },
  {
    name: '接口集成',
    value: parsePercentage(store.snapshot.overview.integrationSuccessPct),
    detail: `${store.snapshot.operations.integrationResult?.toLocaleString() ?? '—'} 笔`,
    tone: 'accent',
  },
]))

const qualityErrorCount = computed<number | null>(() => {
  const quality = store.snapshot.quality
  const values = [quality?.voucherBalanceErrors, quality?.timeOrderErrors, quality?.orphanLinkErrors]
  return values.every((value) => value != null)
    ? values.reduce<number>((sum, value) => sum + Number(value), 0)
    : null
})

const operationalGuardItems = computed(() => [
  { name: '接口失败', value: store.snapshot.operations?.integrationFailed ?? null, tone: 'danger' as const },
  { name: '双轨差异', value: store.snapshot.operations?.dualRunInconsistent ?? null, tone: 'warning' as const },
  { name: '金标异常', value: qualityErrorCount.value, tone: 'accent' as const },
])

const operationalGuardTotal = computed<number | null>(() => {
  const values = operationalGuardItems.value.map((item) => item.value)
  return values.every((value) => value != null)
    ? values.reduce<number>((sum, value) => sum + Number(value), 0)
    : null
})

const operationalGuardOption = computed(() => createOperationalGuardOption(operationalGuardItems.value))

const riskRows = computed<StatusRow[]>(() =>
  (store.snapshot.issues || []).map((item) => ({
    id: `${item.orgName}-${item.type}-${item.title}`,
    title: item.title,
    desc: `${item.area} · ${item.owner} · ${item.status}`,
    dot: true,
    tone: item.level === '高' ? 'danger' : (item.status === '正常' ? 'success' : 'warning'),
  })),
)

const chooseProvince = (name: string) => {
  if (selectedProvince.value === name) {
    selectedProvince.value = '全国'
  } else {
    selectedProvince.value = name
  }
}
</script>

<template>
  <div class="w-full h-full p-3 bg-surface-base flex flex-col gap-2.5 overflow-hidden select-none">
    <!-- A1 顶部高密指标带 (自适应内容高度) -->
    <header class="flex-shrink-0">
      <CockpitTopBar
        :overview="store.snapshot.overview"
        :issues-summary="store.snapshot.issuesSummary"
        :construction="store.snapshot.construction"
        :operations="store.snapshot.operations"
        :live="liveStore.liveOverview"
        :cumulative="liveStore.cumulative"
        :projection-connected="projectionConnected"
        :recent-event="recentEvent"
        :num-duration="numDuration"
        @open-risk="router.push('/f')"
      />
    </header>

    <!-- 每日指挥部智能简报（后台 AI 生成，一行摘要，点击进 F 屏看全文） -->
    <button
      type="button"
      class="h-8 flex-shrink-0 flex items-center justify-center gap-2 px-3 rounded-lg bg-sky-500/10 border border-sky-500/20 text-center hover:bg-sky-500/15 transition-colors cursor-pointer w-full min-w-0 disabled:invisible disabled:pointer-events-none"
      :disabled="!briefingSummary"
      :title="briefingSummary ? '点击查看智能研判全文' : undefined"
      @click="router.push('/f')"
    >
      <span class="flex-shrink-0 font-mono text-cockpit-xs font-bold px-1.5 py-0.5 rounded bg-sky-500/20 text-sky-300 border border-sky-400/30">AI 简报</span>
      <span class="text-cockpit-sm text-slate-300 truncate min-w-0 max-w-4xl">{{ briefingSummary }}</span>
      <ChevronRight :size="13" class="flex-shrink-0 text-sky-400" />
    </button>

    <!-- 三栏主体：严格固定 Grid 物理防爆舱 (左右比例一致，绝对水平对齐) -->
    <main class="flex-1 grid grid-cols-cockpit gap-2.5 min-h-0">
      
      <!-- 左列：A2/A3 承担密集分析，A4 保持紧凑趋势画布 -->
      <aside class="grid grid-rows-dashboard-left gap-2.5 min-h-0">
        <!-- 上部分：拆分为 A2 省域指标与 A3 批次推进 两个独立面板 (A-1) -->
        <div class="grid grid-rows-dashboard-stack gap-2.5 min-h-0">
          <!-- A2: 省域核心指标 -->
          <CockpitPanel
            title="省域核心指标"
            zone="A2"
            :subtitle="selectedProvince === '全国' ? '全国总体概览' : `${selectedProvince}省域下钻`"
            class="min-h-0"
          >
            <template #actions>
              <div class="flex items-center gap-1.5">
                <button
                  v-if="selectedProvince !== '全国'"
                  class="text-cockpit-sm font-medium text-amber-400 hover:text-amber-300 transition-colors flex items-center gap-1 px-2 py-0.5 rounded-lg bg-amber-500/10 border border-amber-500/20 cursor-pointer"
                  @click="selectedProvince = '全国'"
                >
                  返回全国 ✕
                </button>
                <button
                  class="text-cockpit-sm font-medium text-sky-400 hover:text-sky-300 transition-colors flex items-center gap-1 px-2 py-0.5 rounded-lg bg-sky-500/10 border border-sky-500/20 cursor-pointer"
                  @click="router.push('/c')"
                >
                  台账 <ArrowUpRight :size="12" />
                </button>
              </div>
            </template>
            <div class="grid grid-cols-5 items-center gap-2 h-full min-h-0">
              <div class="col-span-2 h-full min-w-0 border-r border-surface-veil-06 pr-2">
                <VChart :option="provinceProfileOption" autoresize class="h-full w-full min-w-0" />
              </div>
              <div class="col-span-3 grid grid-rows-4 h-full divide-y divide-white/5 min-w-0">
                <div class="flex items-center justify-between text-cockpit-sm"><span class="text-slate-400">建设完成率</span><b class="font-mono text-sky-400">{{ selectedProvinceData.progress }}%</b></div>
                <div class="flex items-center justify-between text-cockpit-sm"><span class="text-slate-400">纳入单位</span><b class="font-mono text-slate-100">{{ selectedProvinceData.total }}</b></div>
                <div class="flex items-center justify-between text-cockpit-sm"><span class="text-slate-400">正式上线</span><b class="font-mono text-emerald-400">{{ selectedProvinceData.launched }}</b></div>
                <div class="flex items-center justify-between text-cockpit-sm"><span class="text-slate-400">双轨运行</span><b class="font-mono text-amber-400">{{ selectedProvinceData.dual }}</b></div>
              </div>
            </div>
          </CockpitPanel>

          <!-- A3: 批次推进阶梯 -->
          <CockpitPanel
            title="批次推进阶梯"
            zone="A3"
            subtitle="完成批次合并 · 聚焦在推批次"
            class="flex-1 min-h-0"
          >
            <template #actions>
              <PanelLegend compact :items="[
                { label: '已上线', tone: 'success' },
                { label: '已建设待上线', tone: 'accent' },
                { label: '待完成', tone: 'neutral' },
              ]" />
            </template>
            <VChart :option="batchProgressOption" autoresize class="w-full h-full min-h-0" />
          </CockpitPanel>
        </div>

        <!-- 下部分：A4 上线趋势图 + 最新快照小标注 (A-4) -->
        <CockpitPanel
          title="上线与双轨走势"
          zone="A4"
          :subtitle="`7 个进度节点 · 累计上线 ${store.snapshot.overview.launched ?? 0} 家`"
        >
          <template #actions>
            <PanelLegend compact :items="[
              { label: '正式上线', tone: 'accent' },
              { label: '双轨核对', tone: 'warning' },
            ]" />
          </template>
          <OverviewTrendChart class="w-full h-full min-h-0" :data="store.snapshot.trend" />
        </CockpitPanel>
      </aside>

      <!-- 中列：中国地图沙盘 (A5) -->
      <section class="min-h-0 rounded-xl bg-slate-900/60 border border-white/10 backdrop-blur-md overflow-hidden p-3 flex flex-col gap-2">
        <!-- 地图 header：仅标识，无冗余提示 -->
        <div class="flex items-center gap-2 flex-shrink-0">
          <span class="font-mono text-cockpit-xs font-bold px-1.5 py-0.5 rounded bg-white/5 text-slate-400 border border-white/10 tracking-wide">A5</span>
          <span class="text-cockpit-md font-semibold text-slate-100 tracking-wide">全域推展沙盘</span>
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

      <!-- 右列：运营与风险预警中枢 (比例 1fr : 1.3fr，放大下半风险预警 A-3) -->
      <aside class="grid grid-rows-cockpit-right gap-2.5 min-h-0">
        <!-- 上部分：拆分为 A6 运营质效 与 A8 联系人覆盖 两个独立面板 (A-2) -->
        <div class="flex flex-col gap-2.5 min-h-0">
          <!-- A6: 全网运营质效 -->
          <CockpitPanel
            title="全网运营质效"
            zone="A6"
            subtitle="运行规模与质量对比"
            class="flex-1 min-h-0"
          >
            <div class="grid grid-cols-3 h-full min-h-0 items-stretch">
              <div class="flex flex-col justify-center border-r border-surface-veil-06 pr-2 min-w-0">
                <span class="text-cockpit-xs text-slate-500">双轨运行</span>
                <div class="flex items-baseline gap-1 mt-1">
                  <b class="font-mono text-cockpit-metric text-sky-400">{{ store.snapshot.overview.dual ?? '—' }}</b>
                  <small class="text-cockpit-xs text-slate-500">家</small>
                </div>
                <span class="text-cockpit-xs text-slate-500 mt-1">并行核对中</span>
              </div>
              <VChart :option="operationsQualityOption" autoresize class="col-span-2 w-full h-full min-w-0 pl-2" />
            </div>
          </CockpitPanel>

          <!-- A8: 聚合运营异常，不与 C5 联系人面板重复 -->
          <CockpitPanel
            title="运营红线哨位"
            zone="A8"
            subtitle="接口、核对与金标异常"
            class="flex-shrink-0"
          >
            <div class="grid grid-cols-4 h-20 min-h-0 items-stretch">
              <div class="flex flex-col justify-center border-r border-surface-veil-06 pr-2 min-w-0">
                <span class="text-cockpit-xs text-slate-500">异常总数</span>
                <div class="flex items-baseline gap-1 mt-1">
                  <b
                    class="font-mono text-cockpit-metric"
                    :class="operationalGuardTotal == null ? 'text-slate-400' : (operationalGuardTotal === 0 ? 'text-emerald-400' : 'text-rose-400')"
                  >{{ operationalGuardTotal ?? '—' }}</b>
                  <small class="text-cockpit-xs text-slate-500">项</small>
                </div>
                <span class="text-cockpit-xs mt-1" :class="operationalGuardTotal == null ? 'text-slate-500' : (operationalGuardTotal === 0 ? 'text-emerald-400' : 'text-amber-400')">
                  {{ operationalGuardTotal == null ? '数据未完整' : (operationalGuardTotal === 0 ? '三道门禁通过' : '需要核查') }}
                </span>
              </div>
              <VChart class="col-span-3 w-full h-full min-h-0 pl-2" :option="operationalGuardOption" autoresize />
            </div>
          </CockpitPanel>
        </div>

        <!-- 下部分：扩大面积的 A7 态势监控与风险预警 (A-3) -->
        <CockpitPanel
          title="态势预警与风险处置"
          zone="A7"
          tone="risk"
          subtitle="分级预警台账"
          class="flex flex-col min-h-0"
        >
          <div class="flex flex-col h-full gap-2.5 overflow-hidden">
            <!-- 风险三大核心指标 -->
            <div class="grid grid-cols-3 gap-2 bg-rose-950/20 border border-rose-500/20 rounded-xl p-2 text-center flex-shrink-0">
              <div>
                <div class="text-cockpit-metric font-bold font-mono text-rose-400 leading-tight">
                  {{ store.snapshot.overview.highRisk }}
                </div>
                <div class="text-cockpit-sm text-rose-300/80 font-medium">高风险</div>
              </div>
              <div>
                <div class="text-cockpit-metric font-bold font-mono text-amber-400 leading-tight">
                  {{ store.snapshot.overview.unresolvedIssues }}
                </div>
                <div class="text-cockpit-sm text-amber-300/80 font-medium">未解决</div>
              </div>
              <div>
                <div class="text-cockpit-metric font-bold font-mono text-emerald-400 leading-tight">
                  {{ store.snapshot.issuesSummary?.closeRate ?? 0 }}%
                </div>
                <div class="text-cockpit-sm text-emerald-300/80 font-medium">闭环率</div>
              </div>
            </div>

            <!-- 风险清单列表 (字体用 text-cockpit-sm 保证可读性) -->
            <div class="flex-1 min-h-0 overflow-y-auto pr-1 text-cockpit-sm">
              <StatusList :rows="riskRows" scroll chevron @select="router.push('/f')" />
            </div>

            <!-- 底部进入风险中心操作按钮 -->
            <button
              class="w-full py-2 px-3 rounded-xl text-cockpit-sm font-medium text-rose-300 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 transition-all flex items-center justify-center gap-1.5 mt-auto flex-shrink-0 cursor-pointer shadow-sm"
              @click="router.push('/f')"
            >
              进入风险中心 <ChevronRight :size="14" />
            </button>
          </div>
        </CockpitPanel>
      </aside>

    </main>
  </div>
</template>
