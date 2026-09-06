<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Database,
  FileCheck2,
  TrendingUp,
  ChevronRight,
  ArrowUpRight,
  Users,
} from 'lucide-vue-next'
import ChinaMap from '../components/ChinaMap.vue'
import CockpitTopBar from '../components/CockpitTopBar.vue'
import CockpitPanel from '../components/CockpitPanel.vue'
import OverviewTrendChart from '../components/OverviewTrendChart.vue'
import AnimatedProgress from '../components/AnimatedProgress.vue'
import MetricGrid from '../components/blocks/MetricGrid.vue'
import StatList from '../components/blocks/StatList.vue'
import StatusList from '../components/blocks/StatusList.vue'
import type { MetricItem, StatRow, StatusRow } from '../components/blocks/types.ts'
import { useLiveProjection } from '../composables/useLiveProjection.ts'
import { formatPercent } from '../formatters/metrics.ts'
import { useLiveProjectionStore } from '../stores/liveProjection.ts'
import { useProjectStore } from '../stores/project.ts'

const store = useProjectStore()
const liveStore = useLiveProjectionStore()
const router = useRouter()
const selectedProvince = ref('全国')
const { connected: projectionConnected, recentEvent } = useLiveProjection(liveStore.apply)

// 首屏动效只播放一次：进入页面后关闭数字/进度条的强动效时长，
// 避免省份切换、数据轮询刷新时反复"跳数字+飞入"造成视觉噪音。
const isFirstLoad = ref(true)
onMounted(() => {
  window.setTimeout(() => { isFirstLoad.value = false }, 1200)
})
const numDuration = (ms: number) => (isFirstLoad.value ? ms : 0)

const shortDate = (value?: string) => {
  if (!value) return '—'
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (match) {
    return `${parseInt(match[2], 10)}月${parseInt(match[3], 10)}日`
  }
  return value
}

// 尚未录入项目联系人的纳管单位数量
const contactGapOrgs = computed(() => {
  const total = store.snapshot.overview.orgTotal ?? 0
  const covered = store.snapshot.overview.contactsCoveredOrgs ?? 0
  return Math.max(total - covered, 0)
})

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

const detailItems = computed<MetricItem[]>(() => [
  { label: '纳入单位', value: selectedProvinceData.value.total },
  { label: '正式上线', value: selectedProvinceData.value.launched, tone: 'success' },
  { label: '双轨运行', value: selectedProvinceData.value.dual, tone: 'accent' },
  { label: '建设进度', value: selectedProvinceData.value.progress, unit: '%' },
])

const opsItems = computed<MetricItem[]>(() => [
  {
    label: '双轨运行',
    value: store.snapshot.overview.dual,
    icon: Database,
    hint: '家并行核对中',
  },
  {
    label: '凭证入账率',
    value: formatPercent(store.snapshot.overview.voucherSuccessPct),
    icon: FileCheck2,
    tone: 'success',
    hint: `${store.snapshot.overview.voucherTotal?.toLocaleString()} 张`,
  },
  {
    label: '接口成功率',
    value: formatPercent(store.snapshot.overview.integrationSuccessPct),
    icon: TrendingUp,
    tone: 'warning',
    hint: `${store.snapshot.operations.integrationResult?.toLocaleString()} 笔`,
  },
])

const riskRows = computed<StatusRow[]>(() =>
  (store.snapshot.issues || []).map((item) => ({
    id: `${item.orgName}-${item.type}-${item.title}`,
    title: item.title,
    desc: `${item.area} · ${item.owner} · ${item.status}`,
    dot: true,
    tone: item.level === '高' ? 'danger' : (item.status === '正常' ? 'success' : 'warning'),
  })),
)

const BATCH_STAGES: Record<number, string> = {
  1: '工序7 · 标杆示范',
  2: '工序6 · 稳态优化',
  3: '工序5 · 季结巡检',
  4: '工序4 · 首月巩固',
  5: '工序3 · 脱轨初投',
  6: '工序2 · 双轨冲刺',
  7: '工序1 · 联调赋能',
  8: '工序0 · 动态储备',
}

const batchRows = computed<StatRow[]>(() =>
  (store.snapshot.rollout || []).map((batch) => {
    const stage = BATCH_STAGES[batch.batchId] || (batch as any).stageLabel || '建设推进'
    const isUnstarted = batch.batchId === 8
    return {
      id: batch.name,
      label: batch.name,
      sub: isUnstarted ? `${stage} · 待启动` : (batch.dual > 0 ? `${stage} · ${batch.dual}家双轨` : stage),
      value: isUnstarted ? 0 : batch.launchedPct,
      unit: '%',
      progress: isUnstarted ? 0 : batch.constructionPct,
      progressLabel: isUnstarted ? '未开始 0%' : `建设 ${batch.constructionPct}%`,
      progressAlt: isUnstarted ? 0 : batch.launchedPct,
      progressAltLabel: isUnstarted ? '待纳管' : `上线 ${batch.launchedPct}%`,
    }
  }),
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
        :meta="store.snapshot.meta"
        :issues-summary="store.snapshot.issuesSummary"
        :construction="store.snapshot.construction"
        :live="liveStore.liveOverview"
        :cumulative="liveStore.cumulative"
        :projection-connected="projectionConnected"
        :recent-event="recentEvent"
        :num-duration="numDuration"
        :short-date="shortDate"
        @open-risk="router.push('/d')"
      />
    </header>

    <!-- 三栏主体：严格固定 Grid 物理防爆舱 (左右比例一致，绝对水平对齐) -->
    <main class="flex-1 grid grid-cols-cockpit gap-2.5 min-h-0">
      
      <!-- 左列：推广与推进中枢 (上下 1.15 : 1 分割) -->
      <aside class="grid grid-rows-cockpit-side gap-2.5 min-h-0">
        <!-- 上部分：拆分为 A2 省域指标与 A3 批次推进 两个独立面板 (A-1) -->
        <div class="flex flex-col gap-2.5 min-h-0">
          <!-- A2: 省域核心指标 -->
          <CockpitPanel
            title="省域核心指标"
            zone="A2"
            :subtitle="selectedProvince === '全国' ? '全国总体概览' : `${selectedProvince}省域下钻`"
            class="flex-shrink-0"
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
                  class="text-cockpit-sm font-medium text-sky-400 hover:text-sky-300 transition-colors flex items-center gap-0.5 px-2 py-0.5 rounded-lg bg-sky-500/10 border border-sky-500/20 cursor-pointer"
                  @click="router.push('/c')"
                >
                  单位台账 <ArrowUpRight :size="12" />
                </button>
              </div>
            </template>
            <div class="bg-surface-veil-03 border border-surface-veil-06 rounded-xl p-2">
              <MetricGrid :items="detailItems" :columns="2" size="sm" />
            </div>
          </CockpitPanel>

          <!-- A3: 批次推进阶梯 -->
          <CockpitPanel
            title="批次推进阶梯"
            zone="A3"
            subtitle="全网8批工序推进"
            class="flex-1 min-h-0"
          >
            <div class="flex flex-col h-full min-h-0 overflow-hidden">
              <div class="text-cockpit-sm font-medium text-slate-400 mb-1 flex items-center justify-between flex-shrink-0">
                <span>批次演进状态</span>
                <span class="text-slate-500 font-mono">建设 / 上线</span>
              </div>
              <StatList :rows="batchRows" density="dense" scroll class="flex-1 min-h-0 pr-1" />
            </div>
          </CockpitPanel>
        </div>

        <!-- 下部分：A4 上线趋势图 + 最新快照小标注 (A-4) -->
        <CockpitPanel
          title="上线走势与推进速率"
          zone="A4"
          :subtitle="`近7日平稳推进 · 累计上线 ${store.snapshot.overview.launched ?? 0} 家`"
        >
          <div class="w-full h-full flex flex-col min-h-0 gap-2">
            <OverviewTrendChart class="flex-1 min-h-0" :data="store.snapshot.trend" />
            <!-- A4 数据小标注，消除空旷感 -->
            <div class="flex items-center justify-between text-cockpit-xs text-slate-400 px-2.5 py-1.5 bg-surface-veil-03 rounded-lg border border-surface-veil-06 flex-shrink-0">
              <span>正式上线: <b class="font-mono text-sky-400">{{ store.snapshot.overview.launched }}</b> 家</span>
              <span>双轨核对: <b class="font-mono text-amber-400">{{ store.snapshot.overview.dual }}</b> 家</span>
              <span>数据基线: <b class="font-mono text-slate-300">{{ shortDate(store.snapshot.overview.docsAddedAsOfDate || store.snapshot.meta.asOfDate) }}</b></span>
            </div>
          </div>
        </CockpitPanel>
      </aside>

      <!-- 中列：中国地图沙盘 (A5) -->
      <section class="min-h-0 relative rounded-xl bg-slate-900/60 border border-white/10 backdrop-blur-md overflow-hidden p-3 flex flex-col gap-2">
        <!-- 地图 header：左侧标识，右侧下钻状态/重置，同行不重叠 -->
        <div class="flex items-center justify-between flex-shrink-0">
          <div class="flex items-center gap-2">
            <span class="font-mono text-cockpit-xs font-bold px-1.5 py-0.5 rounded bg-white/5 text-slate-400 border border-white/10 tracking-wide">
              A5
            </span>
            <span class="text-cockpit-md font-semibold text-slate-100 tracking-wide">全域推展沙盘</span>
          </div>
          <!-- 未下钻：淡色提示；已下钻：高亮省名 + 一键重置 -->
          <div class="flex items-center">
            <span v-if="selectedProvince === '全国'" class="text-cockpit-xs text-slate-500">点击省份下钻</span>
            <button
              v-else
              class="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-sky-500/15 hover:bg-sky-500/25 border border-sky-500/25 text-sky-300 hover:text-white transition-all text-cockpit-sm font-medium cursor-pointer backdrop-blur-md"
              @click="selectedProvince = '全国'"
            >
              <b class="text-white">{{ selectedProvince }}</b>
              <span class="text-sky-400/70">· 重置 ✕</span>
            </button>
          </div>
        </div>

        <div class="flex-1 w-full min-h-0 relative">
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
            subtitle="单据凭证质效"
            class="flex-1 min-h-0"
          >
            <div class="flex flex-col h-full min-h-0">
              <MetricGrid :items="opsItems" variant="inline" :columns="1" fill />
            </div>
          </CockpitPanel>

          <!-- A8: 项目联系人覆盖 -->
          <CockpitPanel
            title="项目联系人覆盖"
            zone="A8"
            subtitle="纳管覆盖率"
            class="flex-shrink-0"
          >
            <div class="bg-surface-veil-03 border border-surface-veil-06 rounded-xl p-2.5 flex flex-col gap-1.5">
              <div class="flex items-center justify-between text-cockpit-sm">
                <span class="text-slate-400 flex items-center gap-1.5">
                  <Users :size="14" class="text-emerald-400" /> 联系人覆盖率
                </span>
                <span class="font-semibold text-emerald-400 font-mono text-cockpit-md">
                  {{ store.snapshot.overview.contactsCoveragePct ?? 0 }}%
                </span>
              </div>
              <AnimatedProgress
                :value="store.snapshot.overview.contactsCoveragePct ?? 0"
                color="#34d399"
                :height="4"
                :duration="numDuration(900)"
              />
              <div class="flex items-center justify-between text-cockpit-xs text-slate-400">
                <span>已覆盖 <b class="font-mono text-slate-200">{{ store.snapshot.overview.contactsCoveredOrgs ?? 0 }}</b> 家</span>
                <span v-if="contactGapOrgs > 0" class="text-amber-400/80">缺口 {{ contactGapOrgs }} 家</span>
                <span>总纳管 <b class="font-mono text-slate-200">{{ store.snapshot.overview.orgTotal }}</b> 家</span>
              </div>
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
              <StatusList :rows="riskRows" scroll chevron @select="router.push('/d')" />
            </div>

            <!-- 底部进入风险中心操作按钮 -->
            <button
              class="w-full py-2 px-3 rounded-xl text-cockpit-sm font-medium text-rose-300 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 transition-all flex items-center justify-center gap-1.5 mt-auto flex-shrink-0 cursor-pointer shadow-sm"
              @click="router.push('/d')"
            >
              进入风险中心 <ChevronRight :size="14" />
            </button>
          </div>
        </CockpitPanel>
      </aside>

    </main>
  </div>
</template>
