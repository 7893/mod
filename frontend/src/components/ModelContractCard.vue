<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { GaugeChart } from 'echarts/charts'
import { Cpu, Sparkles } from 'lucide-vue-next'
import { calmAnimation, chartInk, chartPalette } from '../charts/theme.ts'

use([CanvasRenderer, GaugeChart])

const props = defineProps<{
  model: {
    name: string
    type?: string
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

const qualityOption = computed(() => ({
  ...calmAnimation,
  series: [{
    type: 'gauge',
    startAngle: 90,
    endAngle: -270,
    radius: '84%',
    center: ['50%', '50%'],
    silent: true,
    pointer: { show: false },
    progress: {
      show: props.model.quality != null,
      roundCap: true,
      width: 8,
      itemStyle: { color: props.ready ? chartPalette.success : chartPalette.warning },
    },
    axisLine: { lineStyle: { width: 8, color: [[1, chartInk.border]] } },
    axisTick: { show: false },
    splitLine: { show: false },
    axisLabel: { show: false },
    title: { show: true, offsetCenter: [0, '35%'], color: chartInk.textMuted, fontSize: 9 },
    detail: {
      offsetCenter: [0, '-6%'],
      color: chartInk.textPrimary,
      fontFamily: 'monospace',
      fontSize: 14,
      formatter: qualityLabel.value,
    },
    data: [{ value: qualityPercent.value, name: '测试集拟合' }],
  }],
}))
</script>

<template>
  <div
    class="grid grid-cols-12 gap-3 h-full min-h-0 p-2 rounded-xl bg-surface-veil-03 border border-surface-veil-06"
    :title="model.description"
  >
    <VChart
      :key="`${model.type ?? model.name}-${ready}-${model.quality ?? 'empty'}`"
      class="col-span-3 w-full h-full min-h-0"
      :option="qualityOption"
      autoresize
    />

    <div class="col-span-9 flex flex-col justify-center min-w-0 gap-2">
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

      <div class="grid grid-cols-2 gap-2 text-cockpit-xs min-w-0">
        <div class="min-w-0">
          <span class="block text-slate-500">算法</span>
          <b class="block font-mono text-slate-200 truncate mt-0.5">{{ model.algorithm }}</b>
        </div>
        <div class="min-w-0">
          <span class="block text-slate-500">拟合目标</span>
          <code class="block font-mono text-emerald-400 truncate mt-0.5">{{ model.target }}</code>
        </div>
      </div>

      <div class="flex items-center gap-1 overflow-hidden">
        <span
          v-for="feature in model.features.slice(0, 2)"
          :key="feature"
          class="font-mono text-cockpit-xs px-1.5 py-0.5 rounded bg-sky-950/30 text-sky-300 border border-sky-500/20 truncate"
        >
          {{ feature }}
        </span>
        <span v-if="model.features.length > 2" class="text-slate-500 text-cockpit-xs flex-shrink-0">+{{ model.features.length - 2 }} 特征</span>
      </div>

      <div
        class="flex items-center gap-1.5 text-cockpit-xs min-w-0"
        :class="ready ? 'text-emerald-400' : 'text-slate-500'"
      >
        <Cpu :size="13" class="flex-shrink-0" />
        <span class="truncate">{{ ready ? '测试集达标 · 库内推理就绪' : emptyLabel }}</span>
      </div>
    </div>
  </div>
</template>
