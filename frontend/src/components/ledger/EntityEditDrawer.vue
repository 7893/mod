<script setup lang="ts">
import DrawerShell from '../DrawerShell.vue'
import { X } from 'lucide-vue-next'
import type { EntityRow } from '../../stores/project.ts'
import { STATUS_ORDER } from '../../utils/entityOptions.ts'

defineProps<{ entity: EntityRow }>()
const draft = defineModel<Partial<EntityRow>>('draft', { required: true })
const emit = defineEmits<{ (e: 'close'): void; (e: 'save'): void }>()

const fieldClass =
  'px-3 py-1.5 rounded-lg bg-slate-800 border border-white/10 text-slate-200 focus:outline-none focus:border-sky-500/40'
</script>

<template>
  <DrawerShell label="调整单位状态" @close="emit('close')">
      <header class="flex items-center justify-between border-b border-white/5 pb-3">
        <div>
          <span class="font-mono text-cockpit-xs text-sky-400 font-bold">MOD-{{ entity.id }}</span>
          <h3 class="text-cockpit-md font-semibold text-slate-100">调整单位状态</h3>
        </div>
        <button
          type="button"
          aria-label="关闭单位详情"
          class="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-colors cursor-pointer"
          @click="emit('close')"
        >
          <X :size="18" />
        </button>
      </header>

      <div class="p-3 rounded-lg bg-surface-veil-03 border border-surface-veil-06">
        <b class="text-cockpit-md font-semibold text-slate-100 block">{{ entity.name }}</b>
        <span class="text-cockpit-sm text-slate-400 mt-1 block">{{ entity.province }} · {{ entity.batch }}</span>
      </div>

      <form class="flex flex-col gap-3.5 flex-1" @submit.prevent="emit('save')">
        <label class="flex flex-col gap-1 text-cockpit-sm text-slate-300 font-medium">
          运行状态
          <select v-model="draft.status" :class="fieldClass">
            <option v-for="s in STATUS_ORDER" :key="s">{{ s }}</option>
          </select>
        </label>

        <label class="flex flex-col gap-1 text-cockpit-sm text-slate-300 font-medium">
          项目联系人
          <input v-model="draft.owner" :class="fieldClass" />
        </label>

        <label class="flex flex-col gap-1 text-cockpit-sm text-slate-300 font-medium">
          <div class="flex justify-between">
            <span>建设完成率</span>
            <b class="font-mono text-sky-400">{{ draft.construction }}%</b>
          </div>
          <input v-model.number="draft.construction" type="range" min="0" max="100" class="w-full accent-sky-400 cursor-pointer" />
        </label>

        <label class="flex flex-col gap-1 text-cockpit-sm text-slate-300 font-medium">
          <div class="flex justify-between">
            <span>期初数据完成率</span>
            <b class="font-mono text-emerald-400">{{ draft.openingData }}%</b>
          </div>
          <input v-model.number="draft.openingData" type="range" min="0" max="100" class="w-full accent-emerald-400 cursor-pointer" />
        </label>

        <p class="text-cockpit-xs text-slate-500 mt-auto">保存后即时同步快照并记录变更</p>

        <div class="flex items-center gap-2.5 pt-3 border-t border-white/5">
          <button
            type="button"
            class="flex-1 py-1.5 rounded-lg border border-white/10 text-slate-300 hover:bg-white/5 transition-colors text-cockpit-sm font-medium cursor-pointer"
            @click="emit('close')"
          >
            取消
          </button>
          <button
            type="submit"
            class="flex-1 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-medium transition-colors text-cockpit-sm shadow-sm shadow-sky-950 cursor-pointer"
          >
            保存
          </button>
        </div>
      </form>
  </DrawerShell>
</template>
