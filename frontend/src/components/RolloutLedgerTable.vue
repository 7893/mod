<script setup lang="ts">
import { computed, ref } from 'vue'
import { RotateCcw } from 'lucide-vue-next'
import CockpitPanel from './CockpitPanel.vue'
import EntityEditDrawer from './ledger/EntityEditDrawer.vue'
import FilterSelect from './ledger/FilterSelect.vue'
import LedgerPager from './ledger/LedgerPager.vue'
import SearchInput from './ledger/SearchInput.vue'
import { useEntityEditor } from '../composables/useEntityEditor.ts'
import { usePagedList } from '../composables/usePagedList.ts'
import { formatPercent } from '../formatters/metrics.ts'
import { useProjectStore } from '../stores/project.ts'
import {
  ALL,
  BATCH_ORDER,
  NATIONAL_PROVINCE_ORDER,
  countedOptions,
  matchesEntityQuery,
  matchesOption,
} from '../utils/entityOptions.ts'

const store = useProjectStore()
const query = ref('')
const selectedBatch = ref(ALL)
const selectedProvince = ref(ALL)

const provinces = computed(() =>
  countedOptions(store.entities, (row) => row.province, { order: NATIONAL_PROVINCE_ORDER, allLabel: '全部省份' }),
)
const batchOptions = computed(() =>
  countedOptions(store.entities, (row) => row.batch, { order: BATCH_ORDER, allLabel: '全部批次' }),
)

const filteredEntities = computed(() =>
  store.entities.filter(
    (row) =>
      matchesOption(selectedBatch.value, row.batch) &&
      matchesOption(selectedProvince.value, row.province) &&
      matchesEntityQuery(row, query.value),
  ),
)

const { page, totalPages, items: paginatedEntities } = usePagedList(() => filteredEntities.value, {
  pageSize: 20,
  resetOn: [selectedBatch, selectedProvince, query],
})

const isFiltered = computed(() => selectedBatch.value !== ALL || selectedProvince.value !== ALL || !!query.value)

function resetFilters() {
  selectedBatch.value = ALL
  selectedProvince.value = ALL
  query.value = ''
  page.value = 1
}

const { editing, draft, open: openEdit, close: closeEdit, save } = useEntityEditor()
</script>

<template>
  <!-- C6: 单位台账表格与分页 -->
  <CockpitPanel
    title="单位台账"
    zone="C6"
    :subtitle="isFiltered ? `筛选出 ${filteredEntities.length} 家 / 共 ${store.entities.length} 家纳管单位` : `共 ${filteredEntities.length} 家纳管单位`"
    class="flex-1 min-h-0"
  >
    <template #actions>
      <div class="flex items-center gap-2">
        <SearchInput v-model="query" placeholder="搜索单位/联系人/批次/省份" />
        <FilterSelect v-model="selectedBatch" :options="batchOptions" />
        <FilterSelect v-model="selectedProvince" :options="provinces" />
        <button
          v-if="isFiltered"
          type="button"
          class="flex items-center gap-1 px-2.5 py-1 text-cockpit-sm rounded-lg bg-surface-veil-03 border border-surface-veil-06 text-slate-300 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
          title="重置所有筛选条件"
          @click="resetFilters"
        >
          <RotateCcw :size="12" />
          <span>重置</span>
        </button>
      </div>
    </template>

    <div class="flex flex-col h-full min-h-0 justify-between gap-2">
      <div class="flex-1 min-h-0 overflow-y-auto rounded-xl border border-surface-veil-06 bg-surface-veil-03">
        <table class="w-full border-collapse text-cockpit-sm">
          <thead>
            <tr>
              <th class="sticky top-0 bg-slate-900 px-3 py-2 text-left font-medium text-slate-400">编码 / 单位</th>
              <th class="sticky top-0 bg-slate-900 px-3 py-2 text-left font-medium text-slate-400">省份</th>
              <th class="sticky top-0 bg-slate-900 px-3 py-2 text-left font-medium text-slate-400">批次</th>
              <th class="sticky top-0 bg-slate-900 px-3 py-2 text-left font-medium text-slate-400">联系人</th>
              <th class="sticky top-0 bg-slate-900 px-3 py-2 text-left font-medium text-slate-400">状态</th>
              <th class="sticky top-0 bg-slate-900 px-3 py-2 text-left font-medium text-slate-400">建设进度</th>
              <th class="sticky top-0 bg-slate-900 px-3 py-2 text-right font-medium text-slate-400">期初数据</th>
              <th class="sticky top-0 bg-slate-900 px-3 py-2 text-right font-medium text-slate-400">凭证率</th>
              <th class="sticky top-0 bg-slate-900 px-3 py-2 text-left font-medium text-slate-400">更新时间</th>
              <th class="sticky top-0 bg-slate-900 px-3 py-2 text-center font-medium text-slate-400">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in paginatedEntities"
              :key="row.id"
              class="border-t border-surface-veil-06 text-slate-200 hover:bg-white/5 transition-colors"
            >
              <td class="px-3 py-1.5">
                <div class="flex flex-col">
                  <b class="font-medium text-slate-100 truncate max-w-xs">{{ row.name }}</b>
                  <span class="font-mono text-cockpit-xs text-slate-500">MOD-{{ row.id }}</span>
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
                    'bg-slate-800/60 text-slate-400 border-white/10': row.status === '准备中' || row.status === '未启动',
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
              <td class="px-3 py-1.5 text-right font-mono">{{ row.openingData }}%</td>
              <td class="px-3 py-1.5 text-right font-mono">{{ formatPercent(row.voucherRate) }}</td>
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
            <tr v-if="!paginatedEntities.length">
              <td colspan="10" class="px-3 py-10 text-center text-slate-500">
                <div class="flex flex-col items-center justify-center gap-2">
                  <p>无匹配单位记录（当前筛选条件下未检索到数据）</p>
                  <button
                    v-if="isFiltered"
                    type="button"
                    class="px-3 py-1 text-cockpit-xs rounded bg-sky-500/20 text-sky-300 hover:bg-sky-500/30 border border-sky-500/30 transition-colors cursor-pointer"
                    @click="resetFilters"
                  >
                    清除筛选条件并返回全部
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <LedgerPager v-model="page" :total-pages="totalPages" :summary="`共 ${filteredEntities.length} 条`" />
    </div>
  </CockpitPanel>

  <EntityEditDrawer v-if="editing" v-model:draft="draft" :entity="editing" @close="closeEdit" @save="save" />
</template>
