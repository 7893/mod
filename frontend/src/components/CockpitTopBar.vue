<script setup lang="ts">
import { computed } from 'vue'
import { ChevronRight } from 'lucide-vue-next'
import AnimatedNumber from './AnimatedNumber.vue'
import LiveProjectionIndicator from './LiveProjectionIndicator.vue'
import type { LiveProjectionCounts, LiveProjectionEvent } from '../composables/useLiveProjection.ts'
import type { ProjectSnapshot } from '../stores/project.ts'

/**
 * A1 顶部指标带（三分天下架构）：
 * 1. 全域模拟数据总量：单位(2000家)、批次(8批)、单据(505万)、凭证(322万)、数据规模(3184.5万行)、建设进度(63.8%)
 * 2. 今日增量动态：单据、凭证、集成实时跳动 + 最近发生事件单位与省份提示
 * 3. 态势与风险闭环：高风险待处置、未解决、闭环率常驻角标
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
</script>

<template>
  <!-- A1 顶部指标带：三分天下布局 -->
  <section class="cockpit-top-bar zone-region" data-zone="A1">
    <!-- 块一：全域模拟数据总量（展示完整全量模拟资产） -->
    <div class="kpi-cluster kpi-cluster--totals">
      <div class="kpi-cluster__header">
        <span class="kpi-cluster__tag">全域总盘</span>
        <span class="kpi-cluster__title">全域模拟数据总量</span>
        <span class="kpi-cluster__badge">覆盖 34 省级行政区 · 8 批次</span>
      </div>
      <div class="kpi-cluster__items kpi-cluster__items--totals">
        <div class="metric">
          <span class="metric__label">纳管单位</span>
          <div class="metric__value">
            <AnimatedNumber :value="overview.orgTotal || 0" :duration="numDuration(800)" /><small>家</small>
          </div>
          <span class="metric__foot">已上线 {{ overview.launched || 0 }} 家 ({{ overview.launchedPct || 0 }}%)</span>
        </div>

        <div class="metric">
          <span class="metric__label">推广批次</span>
          <div class="metric__value accent">
            <AnimatedNumber :value="8" :duration="numDuration(600)" /><small>批</small>
          </div>
          <span class="metric__foot">1~8批全网贯通</span>
        </div>

        <div class="metric">
          <span class="metric__label">业务单据</span>
          <div class="metric__value">
            <AnimatedNumber :value="live.docsTotal || overview.docsTotal || 0" :duration="700" /><small>笔</small>
          </div>
          <span class="metric__foot">累计全量入库</span>
        </div>

        <div class="metric">
          <span class="metric__label">会计凭证</span>
          <div class="metric__value">
            <AnimatedNumber :value="live.vouchersTotal || overview.vouchersTotal || 0" :duration="700" /><small>张</small>
          </div>
          <span class="metric__foot">入账率 {{ overview.voucherSuccessPct || 0 }}%</span>
        </div>

        <div class="metric">
          <span class="metric__label">数据规模</span>
          <div class="metric__value gold">
            <AnimatedNumber :value="Number(((meta?.fullRows || 0) / 10000).toFixed(1))" :decimals="1" :duration="numDuration(800)" /><small>万行</small>
          </div>
          <span class="metric__foot">{{ (meta?.fullRows || 0).toLocaleString() }} 封版明细</span>
        </div>

        <div class="metric">
          <span class="metric__label">建设进度</span>
          <div class="metric__value gold">
            <AnimatedNumber :value="overview.constructionPct || 0" :decimals="1" :duration="numDuration(800)" /><small>%</small>
          </div>
          <span class="metric__foot">{{ (construction?.totalTasks || 59910).toLocaleString() }} 项任务推进</span>
        </div>
      </div>
    </div>

    <!-- 块二：今日增量与实时动态（随 SSE 实时跳动，显示最近单位事件） -->
    <div class="kpi-cluster kpi-cluster--live">
      <div class="kpi-cluster__header">
        <span class="kpi-cluster__tag kpi-cluster__tag--live">实时链路</span>
        <span class="kpi-cluster__title">今日增量动态</span>
        <LiveProjectionIndicator :connected="projectionConnected" :event="recentEvent" />
      </div>
      <div class="kpi-cluster__items">
        <div class="metric">
          <span class="metric__label">单据</span>
          <div class="metric__value success">
            <span class="metric__sign">+</span><AnimatedNumber :value="live.docsTodayAdded || 0" :duration="500" /><small>笔</small>
          </div>
          <span class="metric__foot">{{ shortDate(live.docsAddedAsOfDate) }}</span>
        </div>
        <div class="metric">
          <span class="metric__label">凭证</span>
          <div class="metric__value success">
            <span class="metric__sign">+</span><AnimatedNumber :value="live.vouchersTodayAdded || 0" :duration="500" /><small>张</small>
          </div>
          <span class="metric__foot">{{ shortDate(live.vouchersAddedAsOfDate) }}</span>
        </div>
        <div class="metric">
          <span class="metric__label">集成</span>
          <div class="metric__value success">
            <span class="metric__sign">+</span><AnimatedNumber :value="cumulative.integrations || 0" :duration="500" /><small>笔</small>
          </div>
          <span class="metric__foot">本次会话</span>
        </div>
      </div>
      <!-- 实时单位动态条（增量来源单位提示） -->
      <div class="live-ticker" :class="{ 'live-ticker--active': !!recentEvent }">
        <template v-if="recentEvent && (recentEvent.unitName || recentEvent.province)">
          <span class="live-ticker__beacon"></span>
          <span class="live-ticker__prov">[{{ recentEvent.province }}]</span>
          <span class="live-ticker__unit" :title="recentEvent.unitName">{{ recentEvent.unitName }}</span>
          <span class="live-ticker__action">{{ eventActionText }}</span>
        </template>
        <template v-else>
          <span class="live-ticker__idle-dot"></span>
          <span class="live-ticker__idle-text">实时流水线持续监听中 · 触发时地图联动</span>
        </template>
      </div>
    </div>

    <!-- 块三：运行态势与风险闭环（可点击进入问题清单） -->
    <div class="kpi-cluster kpi-cluster--risk" @click="$emit('openRisk')">
      <div class="kpi-cluster__header">
        <span class="kpi-cluster__tag kpi-cluster__tag--risk">态势监控</span>
        <span class="kpi-cluster__title">风险预警与闭环</span>
      </div>
      <div class="risk-card-content">
        <div class="risk-primary">
          <div class="risk-dot-pulse"></div>
          <div class="risk-main-stat">
            <div class="risk-val">
              <AnimatedNumber :value="overview.highRisk || 0" :duration="numDuration(600)" />
            </div>
            <span class="risk-txt">高风险待处置</span>
          </div>
        </div>
        <div class="risk-divider"></div>
        <div class="risk-subs">
          <div class="risk-sub-stat">
            <span class="sub-lbl">未解决</span>
            <span class="sub-val">{{ (overview.unresolvedIssues || 0).toLocaleString() }}</span>
          </div>
          <div class="risk-sub-stat">
            <span class="sub-lbl">闭环率</span>
            <span class="sub-val success">{{ issuesSummary?.closeRate ?? '50.0' }}%</span>
          </div>
        </div>
        <ChevronRight :size="14" class="risk-chevron" />
      </div>
    </div>
  </section>
</template>
