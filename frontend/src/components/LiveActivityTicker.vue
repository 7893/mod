<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Activity, ChevronLeft, ChevronRight, Radio } from 'lucide-vue-next'

export interface GovernanceActivity {
  id: number
  issueId: string
  action: string
  actor: string
  detail: string
  timeStr: string
  occurredAt: string
  unitName: string
  province: string
  issueType: string
  status: string
}

const emit = defineEmits<{ (e: 'activities', records: GovernanceActivity[]): void }>()
let pollTimer: ReturnType<typeof setInterval> | null = null
let controller: AbortController | null = null
const unavailable = ref(false)

const activities = ref<GovernanceActivity[]>([])
const currentIndex = ref(0)
const isPaused = ref(false)
let timer: ReturnType<typeof setInterval> | null = null

const currentActivity = computed(() => activities.value[currentIndex.value % activities.value.length] ?? null)

async function fetchActivities() {
  controller?.abort()
  const request = new AbortController()
  controller = request
  try {
    const res = await fetch(`${import.meta.env.BASE_URL}api/governance/recent-activities?limit=10`, { signal: request.signal })
    if (!res.ok) throw new Error('Activity request failed')
    const data = await res.json()
    if (request.signal.aborted) return
    if (!Array.isArray(data)) throw new Error('Invalid activity payload')
    activities.value = data.filter((item): item is GovernanceActivity => item && typeof item.issueId === 'string' && typeof item.detail === 'string' && typeof item.unitName === 'string' && typeof item.occurredAt === 'string')
    currentIndex.value = 0
    unavailable.value = false
    emit('activities', activities.value)
  } catch (err) {
    if (request.signal.aborted) return
    unavailable.value = true
    activities.value = []
    emit('activities', [])
    console.warn('Failed to fetch governance activities:', err)
  }
}

function next() {
  if (activities.value.length > 0) {
    currentIndex.value = (currentIndex.value + 1) % activities.value.length
  }
}

function prev() {
  if (activities.value.length > 0) {
    currentIndex.value = (currentIndex.value - 1 + activities.value.length) % activities.value.length
  }
}

onMounted(() => {
  void fetchActivities()
  pollTimer = setInterval(() => { void fetchActivities() }, 30000)
  timer = setInterval(() => {
    if (!isPaused.value) {
      next()
    }
  }, 6000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  if (pollTimer) clearInterval(pollTimer)
  controller?.abort()
})
</script>

<template>
  <div
    class="flex items-center justify-between gap-3 px-3 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800/80 shadow-inner backdrop-blur text-cockpit-xs text-slate-300 transition-all select-none"
    @mouseenter="isPaused = true"
    @mouseleave="isPaused = false"
  >
    <!-- Left badge & pulse icon -->
    <div class="flex items-center gap-2 flex-shrink-0">
      <span v-if="activities.length" class="relative flex h-2 w-2">
        <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
        <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
      </span>
      <span class="inline-flex items-center gap-1 font-medium text-emerald-400">
        <Radio :size="12" />
        治理自愈动态广播
      </span>
      <span class="text-slate-600">|</span>
    </div>

    <!-- Middle activity stream content with transition -->
    <div v-if="!currentActivity" class="flex-1 min-w-0 truncate text-slate-500">
      {{ unavailable ? '治理活动暂不可用' : '暂无治理活动记录' }}
    </div>
    <div v-else class="flex-1 min-w-0 flex items-center gap-2 overflow-hidden text-ellipsis whitespace-nowrap">
      <span class="font-mono text-slate-400 text-cockpit-xs">[{{ currentActivity.timeStr }}]</span>
      <span class="px-1.5 py-0.5 rounded bg-sky-950/60 border border-sky-500/20 text-sky-300 font-medium">
        {{ currentActivity.unitName }}
      </span>
      <span
        class="px-1.5 py-0.5 rounded text-cockpit-xs font-medium"
        :class="
          currentActivity.status === 'RESOLVED'
            ? 'bg-emerald-950/60 border border-emerald-500/30 text-emerald-300'
            : currentActivity.status === 'VERIFYING'
              ? 'bg-amber-950/60 border border-amber-500/30 text-amber-300'
              : 'bg-indigo-950/60 border border-indigo-500/30 text-indigo-300'
        "
      >
        {{ currentActivity.action }} · {{ currentActivity.actor }}
      </span>
      <span class="text-slate-400 truncate text-cockpit-xs">
        {{ currentActivity.detail }}
      </span>
    </div>

    <!-- Right controls -->
    <div v-if="activities.length" class="flex items-center gap-1.5 flex-shrink-0">
      <span class="text-slate-500 font-mono text-cockpit-xs">
        {{ (currentIndex % activities.length) + 1 }}/{{ activities.length }}
      </span>
      <button
        type="button"
        class="p-0.5 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
        title="上一条"
        @click.stop="prev"
      >
        <ChevronLeft :size="14" />
      </button>
      <button
        type="button"
        class="p-0.5 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
        title="下一条"
        @click.stop="next"
      >
        <ChevronRight :size="14" />
      </button>
    </div>
  </div>
</template>
