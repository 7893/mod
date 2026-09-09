<script setup lang="ts">
defineProps<{ totalPages: number; summary: string; compact?: boolean }>()
const page = defineModel<number>({ required: true })

const buttonClass =
  'rounded bg-surface-veil-03 border border-surface-veil-06 text-slate-300 hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed transition-colors text-cockpit-xs cursor-pointer'
</script>

<template>
  <div
    class="flex items-center justify-between px-1 text-slate-400"
    :class="compact ? 'pt-0.5 text-cockpit-xs' : 'pt-1 text-cockpit-sm'"
  >
    <span>{{ summary }} · 第 {{ page }} / {{ totalPages }} 页</span>
    <div class="flex items-center" :class="compact ? 'gap-1.5' : 'gap-2'">
      <button
        type="button"
        :disabled="page <= 1"
        :class="[buttonClass, compact ? 'px-2 py-0.5' : 'px-2.5 py-1']"
        @click="page--"
      >
        上一页
      </button>
      <button
        type="button"
        :disabled="page >= totalPages"
        :class="[buttonClass, compact ? 'px-2 py-0.5' : 'px-2.5 py-1']"
        @click="page++"
      >
        下一页
      </button>
    </div>
  </div>
</template>
