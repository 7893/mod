<script setup lang="ts">
defineProps<{
  title: string
  zone?: string
  subtitle?: string
  tone?: 'default' | 'risk'
}>()
</script>

<template>
  <section
    class="flex flex-col min-h-0 relative overflow-hidden rounded-xl border transition-colors"
    :class="[
      tone === 'risk'
        ? 'bg-rose-950/20 border-rose-500/30'
        : 'bg-slate-900/60 border-white/10 backdrop-blur-md'
    ]"
    :data-zone="zone"
  >
    <!-- 面板标准头部 -->
    <header class="flex items-center justify-between px-3.5 py-2 border-b border-white/5 flex-shrink-0">
      <div class="flex items-center gap-2 min-w-0">
        <span
          v-if="zone"
          class="font-mono text-cockpit-xs font-bold px-1.5 py-0.5 rounded bg-white/5 text-slate-400 border border-white/10 tracking-wide"
        >
          {{ zone }}
        </span>
        <h3 class="text-cockpit-md font-semibold tracking-wide text-slate-100 truncate">
          {{ title }}
        </h3>
        <span v-if="subtitle" class="text-cockpit-sm text-slate-500 font-normal truncate">
          · {{ subtitle }}
        </span>
      </div>
      <div class="flex items-center gap-2 flex-shrink-0">
        <slot name="actions" />
      </div>
    </header>

    <!-- 面板内容插槽 -->
    <div class="flex-1 min-h-0 p-3 overflow-hidden flex flex-col">
      <slot />
    </div>
  </section>
</template>
