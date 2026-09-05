<script setup lang="ts">
import { Cpu, Sparkles } from 'lucide-vue-next'

defineProps<{
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
</script>

<template>
  <div class="flex flex-col justify-between h-full min-h-0 gap-2">
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

    <p class="text-cockpit-xs text-slate-400 leading-relaxed line-clamp-2">{{ model.description }}</p>

    <div class="flex flex-col gap-1.5 p-2 rounded-xl bg-surface-veil-03 border border-surface-veil-06 text-cockpit-xs text-slate-400 flex-1 min-h-0 justify-between">
      <div class="flex items-center justify-between gap-2">
        <span class="flex-shrink-0">算法：</span>
        <b class="font-mono text-slate-200 truncate text-right">{{ model.algorithm }}</b>
      </div>
      <div class="flex items-center justify-between gap-2">
        <span class="flex-shrink-0">目标：</span>
        <code class="font-mono text-emerald-400 truncate text-right">{{ model.target }}</code>
      </div>
      <div v-if="model.quality" class="flex items-center justify-between gap-2">
        <span class="flex-shrink-0">模型性能：</span>
        <b class="font-mono text-sky-400 truncate text-right">
          {{ (model.quality * 100).toFixed(1) }}%
          <span class="text-slate-400 font-normal">({{ model.target.includes('daily') ? 'R² 拟合优度' : '分类准确率' }})</span>
        </b>
      </div>
      <div v-else class="flex items-center justify-between gap-2">
        <span class="flex-shrink-0">模型性能：</span>
        <b class="font-mono text-slate-400 truncate text-right">—（训练/评分未完成）</b>
      </div>
      <div class="pt-1 border-t border-surface-veil-06">
        <span class="block mb-1 text-slate-500">特征维度：</span>
        <div class="flex flex-wrap gap-1">
          <span
            v-for="feature in model.features"
            :key="feature"
            class="font-mono text-cockpit-xs px-1.5 py-0.5 rounded bg-sky-950/30 text-sky-300 border border-sky-500/20"
          >
            {{ feature }}
          </span>
        </div>
      </div>
    </div>

    <div
      v-if="!ready"
      class="flex items-center justify-center gap-2 py-2 px-3 rounded-xl bg-slate-900/40 border border-dashed border-white/10 text-slate-500 text-cockpit-xs flex-shrink-0"
    >
      <Cpu :size="15" class="opacity-50 text-slate-400" />
      <span>{{ emptyLabel }}</span>
    </div>
  </div>
</template>
