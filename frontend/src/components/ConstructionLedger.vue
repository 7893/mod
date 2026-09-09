<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ArrowLeft, Building, CheckCircle2, Database, Filter, History, RotateCcw } from 'lucide-vue-next'
import CockpitPanel from './CockpitPanel.vue'
import MetricGrid from './blocks/MetricGrid.vue'
import type { MetricItem } from './blocks/types.ts'
import EntityEditDrawer from './ledger/EntityEditDrawer.vue'
import FilterSelect from './ledger/FilterSelect.vue'
import LedgerPager from './ledger/LedgerPager.vue'
import SearchInput from './ledger/SearchInput.vue'
import { useEntityEditor } from '../composables/useEntityEditor.ts'
import { usePagedList } from '../composables/usePagedList.ts'
import { formatCount, formatPercent } from '../formatters/metrics.ts'
import { useProjectStore } from '../stores/project.ts'
import {
  ALL,
  BATCH_ORDER,
  NATIONAL_PROVINCE_ORDER,
  READINESS_ORDER,
  STATUS_ORDER,
  countedOptions,
  matchesEntityQuery,
  matchesOption,
} from '../utils/entityOptions.ts'

const props = defineProps<{
  initialFilter?: string
  initialReadinessFilter?: string
}>()

const emit = defineEmits<{
  (e: 'back'): void
}>()

const store = useProjectStore()
const query = ref('')
const province = ref(ALL)
const selectedBatch = ref(ALL)
const selectedStatus = ref(props.initialFilter || ALL)
const selectedReadiness = ref(props.initialReadinessFilter || ALL)

watch(() => props.initialFilter, (val) => {
  if (val) selectedStatus.value = val
})

watch(() => props.initialReadinessFilter, (val) => {
  if (val) selectedReadiness.value = val
})

const filtered = computed(() =>
  store.entities.filter(
    (row) =>
      matchesOption(province.value, row.province) &&
      matchesOption(selectedBatch.value, row.batch) &&
      matchesOption(selectedStatus.value, row.status) &&
      matchesOption(selectedReadiness.value, row.readinessStatus) &&
      matchesEntityQuery(row, query.value),
  ),
)

const provinces = computed(() =>
  countedOptions(store.entities, (row) => row.province, { order: NATIONAL_PROVINCE_ORDER, allLabel: '全部省份' }),
)
const batches = computed(() =>
  countedOptions(store.entities, (row) => row.batch, { order: BATCH_ORDER, allLabel: '全部批次' }),
)
const statusOptions = computed(() =>
  countedOptions(store.entities, (row) => row.status, { order: STATUS_ORDER, allLabel: '全部状态', includeZero: true }),
)
const readinessOptions = computed(() =>
  countedOptions(store.entities, (row) => row.readinessStatus, {
    order: READINESS_ORDER,
    allLabel: '全部准备度',
    includeZero: true,
    allCount: (_rows, counts) => [...counts.values()].reduce((sum, value) => sum + value, 0),
    allSuffix: '家有数据',
  }),
)

const { page, totalPages, items: paginated } = usePagedList(() => filtered.value, {
  pageSize: 25,
  resetOn: [province, selectedBatch, selectedStatus, selectedReadiness, query],
})

const isFiltered = computed(
  () =>
    province.value !== ALL ||
    selectedBatch.value !== ALL ||
    selectedStatus.value !== ALL ||
    selectedReadiness.value !== ALL ||
    !!query.value,
)

function resetFilters() {
  province.value = ALL
  selectedBatch.value = ALL
  selectedStatus.value = ALL
  selectedReadiness.value = ALL
  query.value = ''
  page.value = 1
}

const summaryItems = computed<MetricItem[]>(() => [
  {
    label: '纳管总单位',
    value: formatCount(store.snapshot.overview.orgTotal),
    unit: '家',
    icon: Building,
    hint: '全量生命周期台账',
  },
  {
    label: '当前筛选结果',
    value: formatCount(filtered.value.length),
    unit: '家',
    tone: 'accent',
    icon: Filter,
    hint: `${((filtered.value.length / (store.entities.length || 1)) * 100).toFixed(1)}% 纳管覆盖`,
  },
  {
    label: '期初数据完成',
    value: formatCount(store.snapshot.construction?.dataReadinessSummary?.verified),
    unit: '家',
    tone: 'success',
    icon: CheckCircle2,
    hint: '已完成数据校验',
  },
  {
    label: '建设完成度',
    value: store.snapshot.construction?.avgProgress ?? '—',
    unit: '%',
    icon: Database,
    hint: '全网加总平均进度',
  },
])

const { editing, draft, open: openEdit, close: closeEdit, save } = useEntityEditor()
</script>

<template>
  <div class="flex flex-col gap-2.5 h-full min-h-0 w-full" data-zone="B-LEDGER">
    <!-- 概览与下钻导航 -->
    <CockpitPanel
      title="数据准备台账与单位状态"
      zone="B6"
      :subtitle="`${formatCount(store.entities.length)} 家单位建设完成度、期初数据状态与审计留痕`"
      class="flex-shrink-0"
    >
      <template #actions>
        <button
          type="button"
          class="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-surface-veil-03 border border-surface-veil-06 text-slate-300 hover:text-white hover:bg-white/10 transition-colors text-cockpit-xs font-medium cursor-pointer"
          @click="emit('back')"
        >
          <ArrowLeft :size="13" />
          <span>返回建设进度全景</span>
        </button>
      </template>
      <MetricGrid :items="summaryItems" variant="inline" :columns="4" />
    </CockpitPanel>

    <!-- 台账主表 -->
    <CockpitPanel
      title="单位建设与期初数据台账"
      zone="B7"
      :subtitle="isFiltered ? `筛选出 ${filtered.length} 家 / 共 ${store.entities.length} 家纳管单位` : `全量纳管单位建设完成度、期初数据与推进状态维护（共 ${store.entities.length} 家）`"
      class="flex-1 min-h-0"
    >
      <template #actions>
        <div class="flex items-center gap-2">
          <SearchInput v-model="query" placeholder="搜索单位、联系人或编码" />
          <FilterSelect v-model="selectedBatch" :options="batches" />
          <FilterSelect v-model="province" :options="provinces" />
          <FilterSelect v-model="selectedStatus" :options="statusOptions" />
          <FilterSelect v-model="selectedReadiness" :options="readinessOptions" />
          <button
            v-if="isFiltered"
            type="button"
            class="flex items-center gap-1 px-2.5 py-1 text-cockpit-xs rounded-lg bg-surface-veil-03 border border-surface-veil-06 text-slate-300 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
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
          <table class="w-full border-collapse text-cockpit-sm text-left">
            <thead>
              <tr class="border-b border-surface-veil-06 text-slate-400 font-medium bg-slate-900/80 sticky top-0 backdrop-blur-sm z-10">
                <th class="px-3 py-2">编码 / 单位</th>
                <th class="px-3 py-2">区域</th>
                <th class="px-3 py-2">批次</th>
                <th class="px-3 py-2">联系人</th>
                <th class="px-3 py-2">状态</th>
                <th class="px-3 py-2">建设进度</th>
                <th class="px-3 py-2 text-right">期初数据 / 准备态</th>
                <th class="px-3 py-2 text-right">凭证率</th>
                <th class="px-3 py-2">更新时间</th>
                <th class="px-3 py-2 text-center">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-surface-veil-06">
              <tr
                v-for="row in paginated"
                :key="row.id"
                class="hover:bg-white/5 transition-colors"
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
                <td class="px-3 py-1.5 text-right">
                  <b class="block font-mono text-slate-300">{{ row.openingData }}%</b>
                  <small class="text-cockpit-xs text-slate-500">{{ row.readinessStatus || '未提供' }}</small>
                </td>
                <td class="px-3 py-1.5 text-right font-mono text-slate-300">{{ formatPercent(row.voucherRate) }}</td>
                <td class="px-3 py-1.5 text-slate-400 font-mono text-cockpit-xs">{{ row.updatedAt }}</td>
                <td class="px-3 py-1.5 text-center">
                  <button
                    type="button"
                    class="px-2.5 py-0.5 rounded bg-sky-500/15 text-sky-400 border border-sky-500/30 hover:bg-sky-500/25 transition-colors text-cockpit-xs font-medium cursor-pointer"
                    @click="openEdit(row)"
                  >
                    调态
                  </button>
                </td>
              </tr>
              <tr v-if="!paginated.length">
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

        <LedgerPager v-model="page" :total-pages="totalPages" :summary="`共 ${filtered.length} 条`" />
      </div>
    </CockpitPanel>

    <!-- 最近操作记录 -->
    <CockpitPanel title="最近操作记录" zone="B8" subtitle="台账变更审计留痕" class="flex-shrink-0">
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

    <EntityEditDrawer v-if="editing" v-model:draft="draft" :entity="editing" @close="closeEdit" @save="save" />
  </div>
</template>
