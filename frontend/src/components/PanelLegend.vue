<script setup lang="ts">
export interface PanelLegendItem {
  label: string
  tone: 'accent' | 'success' | 'warning' | 'danger' | 'neutral'
}

withDefaults(defineProps<{
  items: PanelLegendItem[]
  compact?: boolean
}>(), {
  compact: false,
})

const toneClass: Record<PanelLegendItem['tone'], string> = {
  accent: 'bg-sky-400',
  success: 'bg-emerald-400',
  warning: 'bg-amber-400',
  danger: 'bg-rose-400',
  neutral: 'bg-slate-500',
}
</script>

<template>
  <div class="flex items-center gap-2" role="list" aria-label="图例">
    <span
      v-for="item in items"
      :key="item.label"
      class="flex items-center gap-1 min-w-0"
      role="listitem"
      :title="item.label"
    >
      <span class="w-2 h-2 rounded-sm flex-shrink-0" :class="toneClass[item.tone]" aria-hidden="true"></span>
      <span v-if="!compact" class="text-cockpit-xs text-slate-500 whitespace-nowrap">{{ item.label }}</span>
      <span v-else class="sr-only">{{ item.label }}</span>
    </span>
  </div>
</template>
