<script setup lang="ts">
import { Search } from 'lucide-vue-next'

defineProps<{ placeholder: string; compact?: boolean }>()
const model = defineModel<string>({ required: true })
</script>

<template>
  <label
    class="flex items-center gap-1.5 rounded-lg bg-surface-veil-03 border border-surface-veil-06 text-slate-300 focus-within:border-sky-500/40 transition-colors"
    :class="compact ? 'px-2 py-0.5' : 'px-2.5 py-1'"
  >
    <Search :size="compact ? 12 : 13" class="text-slate-400" />
    <input
      v-model="model"
      :placeholder="placeholder"
      class="bg-transparent border-none outline-none text-slate-200 placeholder:text-slate-500 text-cockpit-xs"
      :class="compact ? 'w-28' : 'w-44'"
    />
  </label>
</template>
