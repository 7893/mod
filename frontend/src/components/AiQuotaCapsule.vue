<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RefreshCw, Sparkles, ShieldCheck, AlertCircle } from 'lucide-vue-next'

export interface QuotaData {
  statDate: string
  callCount: number
  neuronsUsed: number
  dailyLimit: number
  remainingNeurons: number
  usagePct: number
  status: string
}

const quota = ref<QuotaData | null>(null)
const loading = ref(false)

async function fetchQuota() {
  loading.value = true
  try {
    const res = await fetch(`${import.meta.env.BASE_URL}api/governance/ai-quota`)
    if (res.ok) {
      quota.value = await res.json()
    }
  } catch (err) {
    console.warn('Failed to fetch AI quota:', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchQuota()
})
</script>

<template>
  <div
    class="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-surface-veil-03 border border-surface-veil-06 text-cockpit-xs text-slate-300"
    :title="`Cloudflare Workers AI 免费日配额：已用 ${quota?.neuronsUsed ?? 0} / ${quota?.dailyLimit ?? 3000} Neurons ($0.00 零费用硬防护)`"
  >
    <Sparkles :size="11" class="text-sky-400 flex-shrink-0" />
    <span class="font-mono text-slate-400">CF AI</span>

    <div v-if="quota" class="flex items-center gap-1">
      <span class="font-mono text-slate-200">{{ quota.neuronsUsed }}</span>
      <span class="text-slate-500">/</span>
      <span class="font-mono text-slate-400">{{ quota.dailyLimit }}</span>
      <span class="text-slate-500">N</span>

      <span
        class="inline-flex items-center px-1 rounded text-cockpit-xs font-medium"
        :class="quota.status === 'FUSED' ? 'text-amber-400 bg-amber-950/40' : 'text-emerald-400 bg-emerald-950/40'"
      >
        <AlertCircle v-if="quota.status === 'FUSED'" :size="9" class="mr-0.5" />
        <ShieldCheck v-else :size="9" class="mr-0.5" />
        {{ quota.status === 'FUSED' ? '已熔断' : '$0.00保障' }}
      </span>
    </div>
    <div v-else class="text-slate-500 font-mono">
      3000 N 守卫中
    </div>

    <button
      type="button"
      class="p-0.5 text-slate-500 hover:text-slate-300 transition-colors cursor-pointer"
      :class="{ 'animate-spin': loading }"
      title="刷新算力额度"
      @click="fetchQuota"
    >
      <RefreshCw :size="10" />
    </button>
  </div>
</template>
