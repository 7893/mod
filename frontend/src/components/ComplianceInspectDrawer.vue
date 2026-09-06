<script setup lang="ts">
import { X } from 'lucide-vue-next'
import { formatPercent } from '../formatters/metrics.ts'

export interface ComplianceIssueUnit {
  id: number
  name: string
  province: string
  batch: string
  owner: string
  status: string
  construction: number
  openingData: number
  voucherRate: number | null
  level: '高' | '中'
  tags: string[]
  primaryIssue: string
  detailNote: string
}

defineProps<{
  unit: ComplianceIssueUnit | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()
</script>

<template>
  <div v-if="unit" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex justify-end" @click.self="emit('close')">
    <aside class="w-96 h-full bg-slate-900 border-l border-white/10 p-5 flex flex-col gap-4 shadow-2xl overflow-y-auto">
      <header class="flex items-center justify-between border-b border-white/5 pb-3">
        <div>
          <span class="font-mono text-cockpit-xs text-sky-400 font-bold">MOD-{{ unit.id }}</span>
          <h3 class="text-cockpit-md font-semibold text-slate-100">单位合规监督核查</h3>
        </div>
        <button type="button" class="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-colors cursor-pointer" @click="emit('close')">
          <X :size="18" />
        </button>
      </header>

      <div class="p-3 rounded-lg bg-surface-veil-03 border border-surface-veil-06 flex flex-col gap-1">
        <b class="text-cockpit-md font-semibold text-slate-100">{{ unit.name }}</b>
        <span class="text-cockpit-sm text-slate-400">{{ unit.province }} · {{ unit.batch }} · 联系人：{{ unit.owner }}</span>
      </div>

      <div class="flex flex-col gap-2">
        <span class="text-cockpit-sm font-semibold text-slate-300">合规风险标签</span>
        <div class="flex items-center gap-1.5 flex-wrap">
          <span
            v-for="t in unit.tags"
            :key="t"
            class="px-2 py-0.5 rounded text-cockpit-xs font-medium border"
            :class="t === '超期挂账' || t === '票据异常'
              ? 'bg-rose-950/40 text-rose-400 border-rose-500/30'
              : 'bg-amber-950/40 text-amber-400 border-amber-500/30'"
          >
            {{ t }}
          </span>
        </div>
      </div>

      <div class="flex flex-col gap-1.5">
        <span class="text-cockpit-sm font-semibold text-slate-300">监督核查要点（点到为止）</span>
        <p class="text-cockpit-sm text-slate-300 bg-surface-veil-03 p-3 rounded-lg border border-surface-veil-06 leading-relaxed">
          {{ unit.detailNote }}
        </p>
      </div>

      <div class="flex flex-col gap-2">
        <span class="text-cockpit-sm font-semibold text-slate-300">支撑指标事实源</span>
        <div class="grid grid-cols-2 gap-2 text-cockpit-xs">
          <div class="p-2 rounded bg-surface-veil-03 border border-surface-veil-06">
            <span class="text-slate-400 block">建设完成率</span>
            <b class="font-mono text-cockpit-sm text-sky-400">{{ unit.construction }}%</b>
          </div>
          <div class="p-2 rounded bg-surface-veil-03 border border-surface-veil-06">
            <span class="text-slate-400 block">期初数据准备</span>
            <b class="font-mono text-cockpit-sm text-amber-400">{{ unit.openingData }}%</b>
          </div>
          <div class="p-2 rounded bg-surface-veil-03 border border-surface-veil-06">
            <span class="text-slate-400 block">运行状态</span>
            <b class="text-cockpit-sm text-slate-200">{{ unit.status }}</b>
          </div>
          <div class="p-2 rounded bg-surface-veil-03 border border-surface-veil-06">
            <span class="text-slate-400 block">双轨核对率</span>
            <b class="font-mono text-cockpit-sm text-emerald-400">{{ formatPercent(unit.voucherRate) }}</b>
          </div>
        </div>
      </div>

      <div class="mt-auto pt-3 border-t border-white/5">
        <p class="text-cockpit-xs text-slate-500 mb-3">
          * 仅核查建设推进与运行风险事实，不做被建设系统内部逐笔会计审计。
        </p>
        <button
          type="button"
          class="w-full py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-medium transition-colors text-cockpit-sm cursor-pointer"
          @click="emit('close')"
        >
          完成核查
        </button>
      </div>
    </aside>
  </div>
</template>
