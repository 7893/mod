<script setup lang="ts">
import { computed, ref } from 'vue'
import { Search } from 'lucide-vue-next'
import { formatPercent } from '../formatters/metrics.ts'

export interface AtRiskUnit {
  id: number
  name: string
  province: string
  batch: string
  owner: string
  status: string
  construction: number
  openingData: number
  voucherRate: number | null
  riskType: '双轨核对差异' | '建设严重滞后' | '准备期卡顿'
  riskLevel: '高危' | '重点关注'
  reason: string
}

const props = defineProps<{
  units: AtRiskUnit[]
}>()

const query = ref('')
const selectedRiskType = ref('全部类型')
const page = ref(1)
const pageSize = ref(6)

const filteredRiskUnits = computed(() =>
  props.units.filter((u) => {
    const matchType = selectedRiskType.value === '全部类型' || u.riskType === selectedRiskType.value
    const matchQuery = !query.value || `${u.name}${u.province}${u.batch}${u.owner}`.includes(query.value)
    return matchType && matchQuery
  }),
)

const totalRiskPages = computed(() => Math.ceil(filteredRiskUnits.value.length / pageSize.value) || 1)

const paginatedRiskUnits = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredRiskUnits.value.slice(start, start + pageSize.value)
})
</script>

<template>
  <div class="flex flex-col h-full min-h-0 justify-between gap-2">
    <!-- 过滤工具栏 -->
    <div class="flex items-center justify-between gap-2 flex-shrink-0">
      <span class="text-cockpit-xs text-slate-400">
        发现 <b class="font-mono text-rose-400">{{ filteredRiskUnits.length }}</b> 家掉队风险单位
      </span>
      <div class="flex items-center gap-2">
        <label class="flex items-center gap-1.5 px-2 py-0.5 rounded-lg bg-slate-800/80 border border-white/10 text-cockpit-xs text-slate-300">
          <Search :size="12" class="text-slate-400" />
          <input
            v-model="query"
            placeholder="搜索单位/区域/联系人"
            class="bg-transparent border-none outline-none text-slate-200 placeholder-slate-500 w-28 text-cockpit-xs"
          />
        </label>
        <select
          v-model="selectedRiskType"
          class="px-2 py-0.5 rounded-lg bg-slate-800/80 border border-white/10 text-cockpit-xs text-slate-200 focus:outline-none focus:border-sky-500/40"
        >
          <option>全部类型</option>
          <option>双轨核对差异</option>
          <option>建设严重滞后</option>
          <option>准备期卡顿</option>
        </select>
      </div>
    </div>

    <!-- 清单表格 -->
    <div class="flex-1 min-h-0 overflow-y-auto rounded-xl border border-surface-veil-06 bg-surface-veil-03">
      <table class="w-full border-collapse text-cockpit-sm text-left">
        <thead>
          <tr class="border-b border-surface-veil-06 text-slate-400 font-medium bg-slate-900/80 sticky top-0 backdrop-blur-sm z-10">
            <th class="px-2.5 py-1.5">编码 / 单位</th>
            <th class="px-2.5 py-1.5">区域 / 批次</th>
            <th class="px-2.5 py-1.5">掉队风险类型</th>
            <th class="px-2.5 py-1.5 text-right">建设进度</th>
            <th class="px-2.5 py-1.5 text-right">双轨平账</th>
            <th class="px-2.5 py-1.5 text-center">预警等级</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-surface-veil-06">
          <tr
            v-for="u in paginatedRiskUnits"
            :key="u.id"
            class="hover:bg-white/5 transition-colors"
          >
            <td class="px-2.5 py-1">
              <div class="flex flex-col">
                <b class="text-slate-200 font-medium truncate max-w-44">{{ u.name }}</b>
                <small class="font-mono text-cockpit-xs text-slate-500">MOD-{{ u.id }} · {{ u.owner }}</small>
              </div>
            </td>
            <td class="px-2.5 py-1 text-slate-300 text-cockpit-xs">
              <div>{{ u.province }}</div>
              <small class="text-slate-500">{{ u.batch }}</small>
            </td>
            <td class="px-2.5 py-1">
              <span
                class="px-1.5 py-0.5 rounded text-cockpit-xs font-medium border inline-block"
                :class="u.riskType === '双轨核对差异'
                  ? 'bg-rose-950/40 text-rose-400 border-rose-500/30'
                  : (u.riskType === '建设严重滞后'
                    ? 'bg-amber-950/40 text-amber-400 border-amber-500/30'
                    : 'bg-sky-950/40 text-sky-400 border-sky-500/30')"
              >
                {{ u.riskType }}
              </span>
            </td>
            <td class="px-2.5 py-1 text-right font-mono text-slate-300">{{ u.construction }}%</td>
            <td class="px-2.5 py-1 text-right font-mono text-slate-300">{{ formatPercent(u.voucherRate) }}</td>
            <td class="px-2.5 py-1 text-center">
              <span
                class="px-1.5 py-0.5 rounded text-cockpit-xs font-semibold"
                :class="u.riskLevel === '高危' ? 'text-rose-400' : 'text-amber-400'"
              >
                {{ u.riskLevel }}
              </span>
            </td>
          </tr>
          <tr v-if="!paginatedRiskUnits.length">
            <td colspan="6" class="px-3 py-6 text-center text-slate-500">无匹配掉队风险单位</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 分页 -->
    <div class="flex items-center justify-between px-1 pt-0.5 text-cockpit-xs text-slate-400">
      <span>预警困难户 {{ filteredRiskUnits.length }} 家 · 第 {{ page }} / {{ totalRiskPages }} 页</span>
      <div class="flex items-center gap-1.5">
        <button
          type="button"
          :disabled="page <= 1"
          class="px-2 py-0.5 rounded bg-surface-veil-03 border border-surface-veil-06 text-slate-300 hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed transition-colors text-cockpit-xs cursor-pointer"
          @click="page--"
        >
          上一页
        </button>
        <button
          type="button"
          :disabled="page >= totalRiskPages"
          class="px-2 py-0.5 rounded bg-surface-veil-03 border border-surface-veil-06 text-slate-300 hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed transition-colors text-cockpit-xs cursor-pointer"
          @click="page++"
        >
          下一页
        </button>
      </div>
    </div>
  </div>
</template>
