<script setup lang="ts">
import type { CountedOption } from '../../utils/entityOptions.ts'

defineProps<{ options: readonly (CountedOption | string)[]; compact?: boolean }>()
const model = defineModel<string>({ required: true })
</script>

<template>
  <select
    v-model="model"
    class="rounded-lg bg-surface-veil-03 border border-surface-veil-06 text-cockpit-xs text-slate-200 focus:outline-none focus:border-sky-500/40 transition-colors cursor-pointer"
    :class="compact ? 'px-2 py-0.5' : 'px-2.5 py-1'"
  >
    <template v-for="opt in options" :key="typeof opt === 'string' ? opt : opt.value">
      <option v-if="typeof opt === 'string'" class="bg-slate-900 text-slate-200">{{ opt }}</option>
      <option v-else :value="opt.value" class="bg-slate-900 text-slate-200">{{ opt.label }}</option>
    </template>
  </select>
</template>
