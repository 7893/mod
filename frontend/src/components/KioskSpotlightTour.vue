<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Sparkles, Compass, X, ArrowRight, ShieldAlert } from 'lucide-vue-next'

const props = withDefaults(
  defineProps<{
    idleTimeoutMs?: number
  }>(),
  {
    idleTimeoutMs: 45000,
  },
)

const emit = defineEmits<{
  (e: 'inspect', unitName: string): void
}>()

const isKioskActive = ref(false)
const spotlightIndex = ref(0)
let idleTimer: ReturnType<typeof setTimeout> | null = null
let rotateTimer: ReturnType<typeof setInterval> | null = null

const spotlightCases = [
  {
    title: '专班现场重点攻坚',
    unitName: '北方特种装备工业集团',
    province: '辽宁',
    level: '高风险隐患',
    issueType: '超期挂账',
    detail: '因历史在建工程与SAP老科目映射断裂引发平账偏差，集团专项数据清洗专班已驻点攻坚 3 天。',
    actionText: '推进中 · 正在执行坏账重分类补丁',
  },
  {
    title: '最新突破性闭环销项',
    unitName: '西南清洁能源投资集团',
    province: '四川',
    level: '已销项达标',
    issueType: '票据异常',
    detail: '双轨核对分录双方分文不差，一致率达 100%，已解除挂账锁定并成功跃迁为双轨试运行！',
    actionText: '已销项 · 凭证流水平稳接入大盘',
  },
  {
    title: '跨期税率差异智能消缺',
    unitName: '华东现代能源开发公司',
    province: '江苏',
    level: '中度瑕疵',
    issueType: '超预算迹象',
    detail: '外围老系统接口响应超时，核心ERP接口联调团队下发自动转码插件，多阶段工序恢复推进。',
    actionText: '核验中 · 压力测试全量通过',
  },
]

const currentCase = computed(() => spotlightCases[spotlightIndex.value % spotlightCases.length])

function resetIdleTimer() {
  if (idleTimer) clearTimeout(idleTimer)
  if (isKioskActive.value) {
    isKioskActive.value = false
  }
  idleTimer = setTimeout(() => {
    isKioskActive.value = true
  }, props.idleTimeoutMs)
}

function handleUserActivity() {
  if (isKioskActive.value) {
    isKioskActive.value = false
  }
  resetIdleTimer()
}

function dismiss() {
  isKioskActive.value = false
  resetIdleTimer()
}

onMounted(() => {
  window.addEventListener('mousemove', handleUserActivity, { passive: true })
  window.addEventListener('keydown', handleUserActivity, { passive: true })
  window.addEventListener('touchstart', handleUserActivity, { passive: true })
  resetIdleTimer()

  rotateTimer = setInterval(() => {
    if (isKioskActive.value) {
      spotlightIndex.value = (spotlightIndex.value + 1) % spotlightCases.length
    }
  }, 12000)
})

onUnmounted(() => {
  window.removeEventListener('mousemove', handleUserActivity)
  window.removeEventListener('keydown', handleUserActivity)
  window.removeEventListener('touchstart', handleUserActivity)
  if (idleTimer) clearTimeout(idleTimer)
  if (rotateTimer) clearInterval(rotateTimer)
})
</script>

<template>
  <Transition
    enter-active-class="transition duration-300 ease-out"
    enter-from-class="opacity-0 translate-y-4 scale-95"
    enter-to-class="opacity-100 translate-y-0 scale-100"
    leave-active-class="transition duration-200 ease-in"
    leave-from-class="opacity-100 translate-y-0 scale-100"
    leave-to-class="opacity-0 translate-y-4 scale-95"
  >
    <div
      v-if="isKioskActive"
      class="fixed bottom-6 right-6 z-50 w-96 p-4 rounded-xl bg-slate-900/95 border border-sky-500/40 shadow-2xl backdrop-blur-xl text-slate-200"
    >
      <!-- Top header bar -->
      <div class="flex items-center justify-between pb-2 mb-2 border-b border-white/10">
        <div class="flex items-center gap-1.5 text-sky-400 font-medium text-cockpit-xs">
          <Compass :size="14" class="animate-spin text-sky-400" />
          <span>展厅巡航模式 · 治理攻坚聚光灯</span>
        </div>
        <button
          type="button"
          class="text-slate-400 hover:text-white p-0.5 rounded transition-colors"
          title="退出巡航"
          @click.stop="dismiss"
        >
          <X :size="14" />
        </button>
      </div>

      <!-- Content -->
      <div class="space-y-2">
        <div class="flex items-center justify-between">
          <span class="text-cockpit-xs text-amber-400 font-medium flex items-center gap-1">
            <Sparkles :size="12" />
            {{ currentCase.title }}
          </span>
          <span
            class="px-1.5 py-0.5 rounded text-cockpit-xs font-mono"
            :class="
              currentCase.level === '已销项达标'
                ? 'bg-emerald-950/70 border border-emerald-500/40 text-emerald-300'
                : 'bg-amber-950/70 border border-amber-500/40 text-amber-300'
            "
          >
            {{ currentCase.province }} · {{ currentCase.issueType }}
          </span>
        </div>

        <div class="text-sm font-semibold text-slate-100 tracking-wide">
          {{ currentCase.unitName }}
        </div>

        <p class="text-cockpit-xs text-slate-300 line-clamp-3 leading-relaxed">
          {{ currentCase.detail }}
        </p>

        <div class="p-2 rounded-lg bg-slate-800/70 border border-white/5 text-cockpit-xs flex items-center justify-between">
          <span class="text-sky-300 truncate mr-2">{{ currentCase.actionText }}</span>
          <span class="text-slate-500 font-mono flex-shrink-0 text-cockpit-xs">移动鼠标退出</span>
        </div>
      </div>
    </div>
  </Transition>
</template>
