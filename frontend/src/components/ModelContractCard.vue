<script setup lang="ts">
import { computed } from 'vue'
import { Cpu, Sparkles } from 'lucide-vue-next'

const props = defineProps<{
  model: {
    name: string
    algorithm: string
    target: string
    status: string
    features: string[]
    description: string
    quality?: number | null
  }
  emptyLabel: string
  ready: boolean
}>()

const qualityPercent = computed(() => {
  if (props.model.quality == null) return 0
  return Math.max(0, Math.min(100, props.model.quality * 100))
})

const qualityLabel = computed(() => {
  if (props.model.quality == null) return '—'
  return props.model.target.includes('daily')
    ? `R² ${props.model.quality.toFixed(4)}`
    : `Acc ${(props.model.quality * 100).toFixed(1)}%`
})
</script>

<template>
  <div class="flex flex-col h-full min-h-0 gap-2">
    <div class="flex items-center justify-between gap-2">
      <div class="flex items-center gap-1.5 min-w-0">
        <Sparkles :size="14" class="text-sky-400 flex-shrink-0" />
        <b class="text-cockpit-md font-semibold text-slate-100 truncate">{{ model.name }}</b>
      </div>
      <span
        class="text-cockpit-xs font-semibold px-2 py-0.5 rounded border flex-shrink-0"
        :class="ready
          ? 'bg-emerald-950/40 text-emerald-400 border-emerald-500/30'
          : 'bg-amber-950/40 text-amber-400 border-amber-500/30'"
      >
        {{ model.status }}
      </span>
    </div>

    <div class="flex items-stretch gap-3 flex-1 min-h-0">
      <div class="w-24 flex-shrink-0 rounded-lg bg-surface-veil-03 border border-surface-veil-06 p-2 flex flex-col justify-center">
        <span class="text-cockpit-xs text-slate-500">验证质量</span>
        <b class="font-mono text-cockpit-md text-sky-400 mt-1">{{ qualityLabel }}</b>
        <div class="h-1 mt-2 rounded-full bg-white/5 overflow-hidden">
          <div class="h-full rounded-full bg-sky-400" :style="{ width: `${qualityPercent}%` }" />
        </div>
      </div>
      <div class="flex-1 min-w-0 flex flex-col justify-center gap-1.5 text-cockpit-xs">
        <div class="flex items-center justify-between gap-2"><span class="text-slate-500">算法</span><b class="font-mono text-slate-200 truncate">{{ model.algorithm }}</b></div>
        <div class="flex items-center justify-between gap-2"><span class="text-slate-500">目标</span><code class="font-mono text-emerald-400 truncate">{{ model.target }}</code></div>
        <p class="text-slate-400 truncate">{{ model.description }}</p>
        <div class="flex items-center gap-1 overflow-hidden">
          <span
            v-for="feature in model.features.slice(0, 3)"
            :key="feature"
            class="font-mono text-cockpit-xs px-1.5 py-0.5 rounded bg-sky-950/30 text-sky-300 border border-sky-500/20"
          >
            {{ feature }}
          </span>
          <span v-if="model.features.length > 3" class="text-slate-500 flex-shrink-0">+{{ model.features.length - 3 }}</span>
        </div>
      </div>
    </div>

    <div
      class="flex items-center gap-1.5 text-cockpit-xs flex-shrink-0"
      :class="ready ? 'text-emerald-400' : 'text-slate-500'"
    >
      <Cpu :size="13" class="flex-shrink-0" />
      <span class="truncate">{{ ready ? '独立测试集验证达标 · 库内推理就绪' : emptyLabel }}</span>
    </div>
  </div>
</template>
