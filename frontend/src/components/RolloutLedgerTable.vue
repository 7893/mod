<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RotateCcw, Search, X } from 'lucide-vue-next'
import CockpitPanel from './CockpitPanel.vue'
import { formatPercent } from '../formatters/metrics.ts'
import { useProjectStore, type EntityRow, type RolloutStatus } from '../stores/project.ts'

const store = useProjectStore()
const query = ref('')
const selectedBatch = ref('全部')
const selectedProvince = ref('全部')
const editing = ref<EntityRow | null>(null)
const draft = ref<Partial<EntityRow>>({})
const page = ref(1)
const pageSize = ref(20)

const NATIONAL_PROVINCE_ORDER = [
  '北京', '天津', '河北', '山西', '内蒙古',
  '辽宁', '吉林', '黑龙江',
  '上海', '江苏', '浙江', '安徽', '福建', '江西', '山东',
  '河南', '湖北', '湖南', '广东', '广西', '海南',
  '重庆', '四川', '贵州', '云南', '西藏',
  '陕西', '甘肃', '青海', '宁夏', '新疆',
  '香港', '澳门', '台湾',
]

const provinces = computed(() => {
  const counts = new Map<string, number>()
  store.entities.forEach((row) => {
    counts.set(row.province, (counts.get(row.province) || 0) + 1)
  })
  const ordered = NATIONAL_PROVINCE_ORDER.filter((p) => counts.has(p)).map((p) => ({
    value: p,
    label: `${p} (${counts.get(p)}家)`,
  }))
  const remaining = [...counts.keys()]
    .filter((p) => !NATIONAL_PROVINCE_ORDER.includes(p))
    .map((p) => ({
      value: p,
      label: `${p} (${counts.get(p)}家)`,
    }))
  return [
    { value: '全部', label: `全部省份 (${store.entities.length}家)` },
    ...ordered,
    ...remaining,
  ]
})

const BATCH_ORDER = ['第一批', '第二批', '第三批', '第四批', '第五批', '第六批', '第七批', '第八批']
const batchOptions = computed(() => {
  const counts = new Map<string, number>()
  store.entities.forEach((row) => {
    counts.set(row.batch, (counts.get(row.batch) || 0) + 1)
  })
  const ordered = BATCH_ORDER.filter((b) => counts.has(b)).map((b) => ({
    value: b,
    label: `${b} (${counts.get(b)}家)`,
  }))
  return [
    { value: '全部', label: `全部批次 (${store.entities.length}家)` },
    ...ordered,
  ]
})

const filteredEntities = computed(() => {
  return store.entities.filter((row) => {
    const matchBatch = selectedBatch.value === '全部' || row.batch === selectedBatch.value
    const matchProv = selectedProvince.value === '全部' || row.province === selectedProvince.value
    const matchQuery = !query.value || `${row.name}${row.owner}${row.province}${row.batch}`.includes(query.value)
    return matchBatch && matchProv && matchQuery
  })
})

const totalPages = computed(() => Math.ceil(filteredEntities.value.length / pageSize.value) || 1)

// 关键修复：筛选条件变动时强制归位第 1 页，彻底根除“分页死锁”
watch([selectedBatch, selectedProvince, query], () => {
  page.value = 1
})

// 边界保护：总页数变化时安全钳位
watch(totalPages, (newTotal) => {
  if (page.value > newTotal) {
    page.value = Math.max(1, newTotal)
  }
})

const isFiltered = computed(() => (
  selectedBatch.value !== '全部' || selectedProvince.value !== '全部' || !!query.value
))

function resetFilters() {
  selectedBatch.value = '全部'
  selectedProvince.value = '全部'
  query.value = ''
  page.value = 1
}

const paginatedEntities = computed(() => {
  const safePage = Math.min(Math.max(1, page.value), totalPages.value)
  const start = (safePage - 1) * pageSize.value
  return filteredEntities.value.slice(start, start + pageSize.value)
})

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
  <!-- C6: 单位台账表格与分页 -->
  <CockpitPanel
    title="单位台账"
    zone="C6"
    :subtitle="isFiltered ? `筛选出 ${filteredEntities.length} 家 / 共 ${store.entities.length} 家纳管单位` : `共 ${filteredEntities.length} 家纳管单位`"
    class="flex-1 min-h-0"
  >
    <template #actions>
      <div class="flex items-center gap-2">
        <div class="relative flex items-center">
          <Search :size="13" class="absolute left-2.5 text-slate-400 pointer-events-none" />
          <input
            v-model="query"
            placeholder="搜索单位/联系人/批次/省份"
            class="pl-7 pr-2.5 py-1 text-cockpit-sm rounded-lg bg-surface-veil-03 border border-surface-veil-06 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-sky-500/40 w-52 transition-colors"
          />
        </div>
        <select
          v-model="selectedBatch"
          class="px-2.5 py-1 text-cockpit-sm rounded-lg bg-surface-veil-03 border border-surface-veil-06 text-slate-200 focus:outline-none focus:border-sky-500/40 transition-colors"
        >
          <option v-for="b in batchOptions" :key="b.value" :value="b.value">{{ b.label }}</option>
        </select>
        <select
          v-model="selectedProvince"
          class="px-2.5 py-1 text-cockpit-sm rounded-lg bg-surface-veil-03 border border-surface-veil-06 text-slate-200 focus:outline-none focus:border-sky-500/40 transition-colors"
        >
          <option v-for="p in provinces" :key="p.value" :value="p.value">{{ p.label }}</option>
        </select>
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

      <div class="flex items-center justify-between px-1 pt-1 text-cockpit-sm text-slate-400">
        <span>共 {{ filteredEntities.length }} 条 · 第 {{ page }} / {{ totalPages }} 页</span>
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
          <div class="flex justify-between">
            <span>建设完成率</span>
            <b class="font-mono text-sky-400">{{ draft.construction }}%</b>
          </div>
          <input
            v-model.number="draft.construction"
            type="range"
            min="0"
            max="100"
            class="w-full accent-sky-400 cursor-pointer"
          />
        </label>

        <label class="flex flex-col gap-1 text-cockpit-sm text-slate-300 font-medium">
          <div class="flex justify-between">
            <span>期初数据完成率</span>
            <b class="font-mono text-emerald-400">{{ draft.openingData }}%</b>
          </div>
          <input
            v-model.number="draft.openingData"
            type="range"
            min="0"
            max="100"
            class="w-full accent-emerald-400 cursor-pointer"
          />
        </label>

        <p class="text-cockpit-xs text-slate-500 mt-auto">保存后即刻更新当前快照状态</p>

        <div class="flex items-center gap-2.5 pt-3 border-t border-white/5">
          <button
            type="button"
            class="flex-1 py-1.5 rounded-lg border border-white/10 text-slate-300 hover:bg-white/5 transition-colors text-cockpit-sm font-medium cursor-pointer"
            @click="editing = null"
          >
            取消
          </button>
          <button
            type="submit"
            class="flex-1 py-1.5 rounded-lg bg-sky-500 text-slate-950 font-semibold hover:bg-sky-400 transition-colors text-cockpit-sm cursor-pointer"
          >
            保存
          </button>
        </div>
      </form>
    </aside>
  </div>
</template>
