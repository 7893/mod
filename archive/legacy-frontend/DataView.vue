<script setup lang="ts">
import { computed, ref } from 'vue'
import { Building, Filter, History, Search, X } from 'lucide-vue-next'
import CockpitPanel from '../components/CockpitPanel.vue'
import MetricGrid from '../components/blocks/MetricGrid.vue'
import type { MetricItem } from '../components/blocks/types.ts'
import { formatPercent } from '../formatters/metrics.ts'
import { useProjectStore, type EntityRow, type RolloutStatus } from '../stores/project.ts'

const store = useProjectStore()
const query = ref('')
const province = ref('全部')
const selectedBatch = ref('全部')
const page = ref(1)
const pageSize = ref(25)
const editing = ref<EntityRow | null>(null)
const draft = ref<Partial<EntityRow>>({})

const filtered = computed(() => store.entities.filter((row) =>
  (province.value === '全部' || row.province === province.value) &&
  (selectedBatch.value === '全部' || row.batch === selectedBatch.value) &&
  (!query.value || `${row.name}${row.owner}${row.province}${row.batch}`.includes(query.value)),
))

const provinces = computed(() => ['全部', ...new Set(store.entities.map((row) => row.province))])
const batches = computed(() => ['全部', ...new Set(store.entities.map((row) => row.batch))])

const paginated = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filtered.value.slice(start, start + pageSize.value)
})

const totalPages = computed(() => Math.ceil(filtered.value.length / pageSize.value) || 1)

const g1SummaryItems = computed<MetricItem[]>(() => [
  {
    label: '纳管单位',
    value: store.snapshot.overview.orgTotal ? store.snapshot.overview.orgTotal.toLocaleString() : '—',
    unit: '家',
    icon: Building,
  },
  {
    label: '当前筛选',
    value: filtered.value.length.toLocaleString(),
    unit: '条',
    tone: 'accent',
    icon: Filter,
  },
])

function openEdit(row: EntityRow) {
  editing.value = row
  draft.value = { ...row }
}

function save() {
  if (!editing.value) return
  store.updateEntity(editing.value.id, {
    status: draft.value.status as RolloutStatus,
    construction: Number(draft.value.construction),
    openingData: Number(draft.value.openingData),
    owner: String(draft.value.owner),
  })
  editing.value = null
}
</script>

<template>
  <div class="flex flex-col gap-2.5 h-full min-h-0 w-full" data-zone="G">
    <!-- G1: 概览 -->
    <CockpitPanel
      title="建设推广项目台账"
      zone="G1"
      :subtitle="`${store.entities.length.toLocaleString()} 家纳管单位全生命周期台账检索与状态维护`"
      class="flex-shrink-0"
    >
      <MetricGrid :items="g1SummaryItems" variant="inline" :columns="2" />
    </CockpitPanel>

    <!-- G2: 台账主表 -->
    <CockpitPanel
      title="单位建设与推广状态"
      zone="G2"
      subtitle="全量纳管单位建设完成度与期初数据台账"
      class="flex-1 min-h-0"
    >
      <template #actions>
        <div class="flex items-center gap-2 flex-wrap">
          <label class="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-800/80 border border-white/10 text-cockpit-xs text-slate-300">
            <Search :size="13" class="text-slate-400" />
            <input
              v-model="query"
              placeholder="搜索单位或联系人"
              class="bg-transparent border-none outline-none text-slate-200 placeholder-slate-500 w-36 text-cockpit-xs"
            />
          </label>
          <select
            v-model="selectedBatch"
            class="px-2.5 py-1 rounded-lg bg-slate-800/80 border border-white/10 text-cockpit-xs text-slate-200 focus:outline-none focus:border-sky-500/40"
          >
            <option v-for="b in batches" :key="b">{{ b === '全部' ? '全部批次' : b }}</option>
          </select>
          <select
            v-model="province"
            class="px-2.5 py-1 rounded-lg bg-slate-800/80 border border-white/10 text-cockpit-xs text-slate-200 focus:outline-none focus:border-sky-500/40"
          >
            <option v-for="p in provinces" :key="p">{{ p === '全部' ? '全部省份' : p }}</option>
          </select>
        </div>
      </template>

      <div class="flex flex-col h-full min-h-0 justify-between gap-2">
        <div class="flex-1 min-h-0 overflow-y-auto rounded-xl border border-surface-veil-06 bg-surface-veil-03">
          <table class="w-full border-collapse text-cockpit-sm text-left">
            <thead>
              <tr class="border-b border-surface-veil-06 text-slate-400 font-medium bg-slate-900/80 sticky top-0 backdrop-blur-sm z-10">
                <th class="px-3 py-2">编码 / 单位</th>
                <th class="px-3 py-2">区域</th>
                <th class="px-3 py-2">批次</th>
                <th class="px-3 py-2">联系人</th>
                <th class="px-3 py-2">状态</th>
                <th class="px-3 py-2">建设进度</th>
                <th class="px-3 py-2 text-right">期初数据</th>
                <th class="px-3 py-2 text-right">凭证率</th>
                <th class="px-3 py-2">更新时间</th>
                <th class="px-3 py-2 text-center">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-surface-veil-06">
              <tr
                v-for="row in paginated"
                :key="row.id"
                class="hover:bg-white/[0.02] transition-colors"
              >
                <td class="px-3 py-1.5">
                  <div class="flex flex-col">
                    <b class="text-slate-200 font-medium">{{ row.name }}</b>
                    <small class="font-mono text-cockpit-xs text-slate-500">MOD-{{ row.id }}</small>
                  </div>
                </td>
                <td class="px-3 py-1.5 text-slate-300">{{ row.province }}</td>
                <td class="px-3 py-1.5 text-slate-300">{{ row.batch }}</td>
                <td class="px-3 py-1.5 font-medium text-slate-300">
                  <span class="px-1.5 py-0.5 rounded bg-white/5 text-slate-300 border border-white/5">{{ row.owner }}</span>
                </td>
                <td class="px-3 py-1.5">
                  <span
                    class="px-2 py-0.5 rounded text-cockpit-xs font-medium border"
                    :class="{
                      'bg-emerald-950/40 text-emerald-400 border-emerald-500/30': row.status === '已上线',
                      'bg-sky-950/40 text-sky-400 border-sky-500/30': row.status === '双轨运行',
                      'bg-amber-950/40 text-amber-400 border-amber-500/30': row.status === '建设中',
                      'bg-slate-800/60 text-slate-400 border-white/10': row.status === '准备中',
                    }"
                  >
                    {{ row.status }}
                  </span>
                </td>
                <td class="px-3 py-1.5">
                  <div class="flex items-center gap-2">
                    <div class="w-16 h-1.5 rounded-full bg-slate-800 overflow-hidden">
                      <div class="h-full rounded-full bg-sky-400" :style="{ width: `${row.construction}%` }" />
                    </div>
                    <span class="font-mono text-cockpit-xs text-slate-300">{{ row.construction }}%</span>
                  </div>
                </td>
                <td class="px-3 py-1.5 text-right font-mono text-slate-300">{{ row.openingData }}%</td>
                <td class="px-3 py-1.5 text-right font-mono text-slate-300">{{ formatPercent(row.voucherRate) }}</td>
                <td class="px-3 py-1.5 text-slate-400 font-mono text-cockpit-xs">{{ row.updatedAt }}</td>
                <td class="px-3 py-1.5 text-center">
                  <button
                    class="px-2.5 py-0.5 rounded bg-sky-500/15 text-sky-400 border border-sky-500/30 hover:bg-sky-500/25 transition-colors text-cockpit-xs font-medium cursor-pointer"
                    @click="openEdit(row)"
                  >
                    调态
                  </button>
                </td>
              </tr>
              <tr v-if="!paginated.length">
                <td colspan="10" class="px-3 py-8 text-center text-slate-500">无匹配单位记录</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="flex items-center justify-between px-1 pt-1 text-cockpit-sm text-slate-400">
          <span>共 {{ filtered.length }} 条 · 第 {{ page }} / {{ totalPages }} 页</span>
          <div class="flex items-center gap-2">
            <button
              :disabled="page <= 1"
              class="px-2.5 py-1 rounded bg-surface-veil-03 border border-surface-veil-06 text-slate-300 hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed transition-colors text-cockpit-xs cursor-pointer"
              @click="page--"
            >
              上一页
            </button>
            <button
              :disabled="page >= totalPages"
              class="px-2.5 py-1 rounded bg-surface-veil-03 border border-surface-veil-06 text-slate-300 hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed transition-colors text-cockpit-xs cursor-pointer"
              @click="page++"
            >
              下一页
            </button>
          </div>
        </div>
      </div>
    </CockpitPanel>

    <!-- G3: 最近操作记录 -->
    <CockpitPanel title="最近操作记录" zone="G3" subtitle="台账变更审计日志" class="flex-shrink-0">
      <template #actions><History :size="16" class="text-slate-400" /></template>
      <div class="flex flex-col gap-1.5 divide-y divide-surface-veil-06">
        <div v-for="audit in store.audits.slice(0, 5)" :key="audit.id" class="flex items-center gap-3 py-1 text-cockpit-xs text-slate-300 flex-wrap">
          <span class="font-mono text-slate-500">{{ audit.time }}</span>
          <b class="font-semibold text-slate-100">{{ audit.operator }}</b>
          <span class="text-slate-400">修改「{{ audit.entity }}」{{ audit.field }}</span>
          <del class="text-rose-400 font-mono">{{ audit.before }}</del>
          <span class="text-slate-600">→</span>
          <ins class="text-emerald-400 font-mono no-underline">{{ audit.after }}</ins>
        </div>
      </div>
    </CockpitPanel>

    <!-- 编辑抽屉 -->
    <div v-if="editing" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex justify-end" @click.self="editing = null">
      <aside class="w-96 h-full bg-slate-900 border-l border-white/10 p-5 flex flex-col gap-4 shadow-2xl overflow-y-auto">
        <header class="flex items-center justify-between border-b border-white/5 pb-3">
          <div>
            <span class="font-mono text-cockpit-xs text-sky-400 font-bold">MOD-{{ editing.id }}</span>
            <h3 class="text-cockpit-md font-semibold text-slate-100">调整单位状态</h3>
          </div>
          <button class="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-colors cursor-pointer" @click="editing = null">
            <X :size="18" />
          </button>
        </header>

        <div class="p-3 rounded-lg bg-surface-veil-03 border border-surface-veil-06">
          <b class="text-cockpit-md font-semibold text-slate-100 block">{{ editing.name }}</b>
          <span class="text-cockpit-sm text-slate-400 mt-1 block">{{ editing.province }} · {{ editing.batch }}</span>
        </div>

        <form class="flex flex-col gap-3.5 flex-1" @submit.prevent="save">
          <label class="flex flex-col gap-1 text-cockpit-sm text-slate-300 font-medium">
            运行状态
            <select
              v-model="draft.status"
              class="px-3 py-1.5 rounded-lg bg-slate-800 border border-white/10 text-slate-200 focus:outline-none focus:border-sky-500/40"
            >
              <option>准备中</option>
              <option>建设中</option>
              <option>双轨运行</option>
              <option>已上线</option>
            </select>
          </label>

          <label class="flex flex-col gap-1 text-cockpit-sm text-slate-300 font-medium">
            项目联系人
            <input
              v-model="draft.owner"
              class="px-3 py-1.5 rounded-lg bg-slate-800 border border-white/10 text-slate-200 focus:outline-none focus:border-sky-500/40"
            />
          </label>

          <label class="flex flex-col gap-1 text-cockpit-sm text-slate-300 font-medium">
            建设完成率
            <div class="flex items-center gap-3">
              <input v-model="draft.construction" type="range" min="0" max="100" class="flex-1 accent-sky-400" />
              <b class="font-mono text-cockpit-sm text-sky-400 w-10 text-right">{{ draft.construction }}%</b>
            </div>
          </label>

          <label class="flex flex-col gap-1 text-cockpit-sm text-slate-300 font-medium">
            期初数据完成率
            <div class="flex items-center gap-3">
              <input v-model="draft.openingData" type="range" min="0" max="100" class="flex-1 accent-sky-400" />
              <b class="font-mono text-cockpit-sm text-sky-400 w-10 text-right">{{ draft.openingData }}%</b>
            </div>
          </label>

          <p class="text-cockpit-xs text-slate-500 mt-2">保存后即时同步并记录变更</p>

          <div class="flex items-center gap-2 mt-auto pt-4 border-t border-white/5">
            <button
              type="button"
              class="flex-1 py-1.5 rounded-lg border border-white/10 text-slate-300 hover:bg-white/5 transition-colors text-cockpit-sm font-medium cursor-pointer"
              @click="editing = null"
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
      </aside>
    </div>
  </div>
</template>
