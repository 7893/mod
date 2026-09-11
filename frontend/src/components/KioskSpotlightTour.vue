<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Sparkles, Compass, X, ArrowRight } from 'lucide-vue-next'

import type { GovernanceActivity } from './LiveActivityTicker.vue'

const props = withDefaults(
  defineProps<{
    idleTimeoutMs?: number
    activities?: GovernanceActivity[]
    suspended?: boolean
  }>(),
  {
    idleTimeoutMs: 45000,
    activities: () => [],
    suspended: false,
  },
)

const emit = defineEmits<{
  (e: 'inspect', issueId: string): void
}>()

const isKioskActive = ref(false)
const spotlightIndex = ref(0)
let idleTimer: ReturnType<typeof setTimeout> | null = null
let rotateTimer: ReturnType<typeof setInterval> | null = null

const currentCase = computed(() => props.activities[spotlightIndex.value % props.activities.length] ?? null)

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
    if (isKioskActive.value && props.activities.length) {
      spotlightIndex.value = (spotlightIndex.value + 1) % props.activities.length
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
      v-if="isKioskActive && currentCase && !suspended"
      @mousemove.stop
      @keydown.stop
      @touchstart.stop
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
      <div class="space-y-2" :data-issue-id="currentCase.issueId">
        <div class="flex items-center justify-between">
          <span class="text-cockpit-xs text-amber-400 font-medium flex items-center gap-1">
            <Sparkles :size="12" />
            {{ currentCase.action }}
          </span>
          <span
            class="px-1.5 py-0.5 rounded text-cockpit-xs font-mono"
            :class="
              ['RESOLVED', 'CLOSED'].includes(currentCase.status)
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
          <span class="text-sky-300 truncate mr-2">{{ currentCase.occurredAt }}</span>
          <span class="text-slate-500 font-mono flex-shrink-0 text-cockpit-xs">移出浮窗退出</span>
        </div>
        <button type="button" class="flex items-center gap-1 text-sky-300 text-cockpit-sm" @click="emit('inspect', currentCase.issueId); dismiss()">查看工单 <ArrowRight :size="14" /></button>
      </div>
    </div>
  </Transition>
</template>
