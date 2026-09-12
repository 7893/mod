<script setup lang="ts">
import CompositionBar from './CompositionBar.vue'
import { formatCount } from '../../formatters/metrics.ts'
import type { CompositionTone } from '../../charts/panelData.ts'

defineProps<{
  primary: {
    label: string
    value: string | number
    unit?: string
    hint: string
    tone?: 'accent' | 'success' | 'warning'
  }
  chartLabel: string
  total: number
  parts: Array<{
    label: string
    value: number
    percentage: number
    tone: CompositionTone
  }>
  facts: Array<{ label: string; value: string | number; unit?: string }>
}>()

const valueClasses = {
  accent: 'text-sky-400',
  success: 'text-emerald-400',
  warning: 'text-amber-400',
}
</script>

<template>
  <div class="grid grid-cols-12 gap-3 h-20 min-h-0 items-stretch">
    <div class="col-span-2 flex flex-col justify-center items-center text-center border-r border-surface-veil-06 px-2 min-w-0">
      <span class="text-cockpit-sm text-slate-400">{{ primary.label }}</span>
      <div class="flex items-baseline justify-center gap-1 mt-1">
        <b class="font-mono text-cockpit-metric" :class="valueClasses[primary.tone || 'accent']">{{ primary.value }}</b>
        <small v-if="primary.unit" class="text-cockpit-xs text-slate-500">{{ primary.unit }}</small>
      </div>
      <span class="text-cockpit-xs text-slate-500 mt-1 truncate">{{ primary.hint }}</span>
    </div>

    <div class="col-span-7 flex flex-col justify-center px-1 min-w-0">
      <div class="flex items-center justify-between mb-1 text-cockpit-xs">
        <span class="text-slate-400">{{ chartLabel }}</span>
        <span class="font-mono text-slate-500">总计 {{ formatCount(total) }}</span>
      </div>
      <CompositionBar :total="total" :parts="parts" />
    </div>

    <div class="col-span-3 grid grid-cols-3 gap-2 border-l border-surface-veil-06 pl-3 min-w-0">
      <div v-for="fact in facts" :key="fact.label" class="flex flex-col justify-center items-center text-center min-w-0">
        <span class="text-cockpit-xs text-slate-500 truncate">{{ fact.label }}</span>
        <b class="font-mono text-cockpit-md text-slate-200 mt-1 truncate">{{ fact.value }}<small v-if="fact.unit" class="text-cockpit-xs text-slate-500 ml-0.5">{{ fact.unit }}</small></b>
      </div>
    </div>
  </div>
</template>
