<script setup lang="ts">
import { computed } from 'vue'
import { formatCount } from '../../formatters/metrics.ts'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import type { CompositionTone } from '../../charts/panelData.ts'
import { createOverviewCompositionOption } from '../../charts/panelOptions.ts'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent])

const props = defineProps<{
  total: number
  parts: Array<{
    label: string
    value: number
    percentage: number
    tone: CompositionTone
  }>
}>()

const option = computed(() => createOverviewCompositionOption(props.parts, props.total))

const dotClasses: Record<CompositionTone, string> = {
  accent: 'bg-sky-400',
  success: 'bg-emerald-400',
  warning: 'bg-amber-400',
  danger: 'bg-rose-400',
  neutral: 'bg-slate-500',
}
</script>

<template>
  <div class="flex flex-col gap-1.5 min-w-0">
    <VChart :option="option" autoresize class="w-full h-7 flex-shrink-0" />
    <div class="flex items-center justify-between gap-2 text-cockpit-xs min-w-0">
      <div v-for="part in parts" :key="part.label" class="flex items-center gap-1 min-w-0">
        <span class="w-1.5 h-1.5 rounded-full flex-shrink-0" :class="dotClasses[part.tone]" />
        <span class="text-slate-400 truncate">{{ part.label }}</span>
        <b class="font-mono text-slate-200 flex-shrink-0">{{ formatCount(part.value) }}</b>
      </div>
    </div>
  </div>
</template>
