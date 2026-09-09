<script setup lang="ts">
import type { Component } from 'vue'
import type { BlockTone } from './types.ts'

withDefaults(defineProps<{ icon?: Component; tone?: BlockTone }>(), { tone: 'default' })

const toneClass: Record<BlockTone, string> = {
  default: 'bg-slate-800/60 border-white/10 text-slate-400',
  accent: 'bg-sky-500/10 border-sky-500/20 text-sky-300',
  success: 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300',
  warning: 'bg-amber-500/10 border-amber-500/20 text-amber-300',
  danger: 'bg-rose-500/10 border-rose-500/20 text-rose-300',
}
const iconClass: Record<BlockTone, string> = {
  default: 'text-sky-400',
  accent: 'text-sky-400',
  success: 'text-emerald-400',
  warning: 'text-amber-400',
  danger: 'text-rose-400',
}
</script>

<template>
  <div class="flex items-center gap-1.5 px-2.5 py-1 rounded border text-cockpit-xs flex-shrink-0" :class="toneClass[tone]">
    <component :is="icon" v-if="icon" :size="13" class="flex-shrink-0" :class="iconClass[tone]" />
    <slot />
  </div>
</template>
