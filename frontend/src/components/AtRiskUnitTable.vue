<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Search, X } from 'lucide-vue-next'
import { formatPercent } from '../formatters/metrics.ts'

export interface RiskAttribution {
  factor: string
  factorName: string
  weightPct: number
  attribution: number
  description: string
}

interface RiskExplanation {
  status: string
  explanationSource: 'HEATWAVE_SHAP' | 'RULE_BASED' | 'UNAVAILABLE'
  topAttributions: RiskAttribution[]
  stagnantDays?: number | null
  progressSlope14d?: number | null
  trainingErrorScissors?: number | null
  handlerConcentration?: number | null
}

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
  stagnantDays?: number
  progressSlope14d?: number
  trainingErrorScissors?: number
  handlerConcentration?: number
  topAttributions?: RiskAttribution[]
}

const props = defineProps<{
  units: AtRiskUnit[]
}>()

const query = ref('')
const selectedRiskType = ref('全部类型')
const page = ref(1)
const pageSize = ref(6)

const selectedUnit = ref<AtRiskUnit | null>(null)
const loadingExplanation = ref(false)
const unitExplanations = ref<Record<number, RiskExplanation>>({})
let explanationSequence = 0
let explanationController: AbortController | null = null

async function openDrawer(u: AtRiskUnit) {
  selectedUnit.value = u
  if (unitExplanations.value[u.id]) {
    return
  }
  const sequence = ++explanationSequence
  explanationController?.abort()
  const controller = new AbortController()
  explanationController = controller
  loadingExplanation.value = true
  try {
    const res = await fetch(`${import.meta.env.BASE_URL}api/insights/risk-explanation/${u.id}`, {
      signal: controller.signal,
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json() as Partial<RiskExplanation>
    if (sequence !== explanationSequence || selectedUnit.value?.id !== u.id) return
    unitExplanations.value[u.id] = {
      status: data.status || 'unavailable',
      explanationSource: data.explanationSource || 'UNAVAILABLE',
      topAttributions: Array.isArray(data.topAttributions) ? data.topAttributions : [],
      stagnantDays: data.stagnantDays,
      progressSlope14d: data.progressSlope14d,
      trainingErrorScissors: data.trainingErrorScissors,
      handlerConcentration: data.handlerConcentration,
    }
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') return
    if (sequence === explanationSequence) {
      unitExplanations.value[u.id] = {
        status: 'unavailable',
        explanationSource: 'UNAVAILABLE',
        topAttributions: [],
      }
    }
    console.warn('Failed to fetch risk explanation:', err)
  } finally {
    if (sequence === explanationSequence) loadingExplanation.value = false
  }
}

const currentExplanation = computed(() => (
  selectedUnit.value ? unitExplanations.value[selectedUnit.value.id] : undefined
))
const currentAttributions = computed<RiskAttribution[]>(() => currentExplanation.value?.topAttributions || [])
const isNativeShap = computed(() => currentExplanation.value?.explanationSource === 'HEATWAVE_SHAP')
const explanationTitle = computed(() => (
  isNativeShap.value ? 'HeatWave AutoML 归因分解' : '规则风险研判'
))

const filteredRiskUnits = computed(() =>
  props.units.filter((u) => {
    const matchType = selectedRiskType.value === '全部类型' || u.riskType === selectedRiskType.value
    const matchQuery = !query.value || `${u.name}${u.province}${u.batch}${u.owner}`.includes(query.value)
    return matchType && matchQuery
  }),
)

const totalRiskPages = computed(() => Math.ceil(filteredRiskUnits.value.length / pageSize.value) || 1)

watch([query, selectedRiskType], () => { page.value = 1 })
watch(totalRiskPages, (total) => {
  if (page.value > total) page.value = total
})

const paginatedRiskUnits = computed(() => {
  const safePage = Math.min(Math.max(1, page.value), totalRiskPages.value)
  const start = (safePage - 1) * pageSize.value
  return filteredRiskUnits.value.slice(start, start + pageSize.value)
})
</script>

<template>
  <div class="flex flex-col h-full min-h-0 justify-between gap-2">
    <!-- 过滤工具栏 -->
    <div class="flex items-center justify-between gap-2 flex-shrink-0">
      <span class="text-cockpit-xs text-slate-400">
        发现 <b class="font-mono text-rose-400">{{ filteredRiskUnits.length }}</b> 家掉队风险单位（点击查看可用解释）
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
            class="hover:bg-white/5 transition-colors cursor-pointer"
            @click="openDrawer(u)"
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

    <!-- 掉队风险 SHAP 归因下钻抽屉 -->
    <div
      v-if="selectedUnit"
      class="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex justify-end"
      @click.self="selectedUnit = null"
    >
      <aside class="w-96 h-full bg-slate-900 border-l border-white/10 p-5 flex flex-col gap-4 shadow-2xl overflow-y-auto">
        <header class="flex items-center justify-between border-b border-white/5 pb-3">
          <div>
            <span class="font-mono text-cockpit-xs text-sky-400 font-bold">MOD-{{ selectedUnit.id }}</span>
            <h3 class="text-cockpit-md font-semibold text-slate-100">掉队风险解释</h3>
          </div>
          <button
            type="button"
            class="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-colors cursor-pointer"
            @click="selectedUnit = null"
          >
            <X :size="18" />
          </button>
        </header>

        <!-- 单位概况 -->
        <div class="p-3 rounded-lg bg-surface-veil-03 border border-surface-veil-06 flex flex-col gap-1">
          <div class="flex items-center justify-between">
            <b class="text-cockpit-md font-semibold text-slate-100 truncate">{{ selectedUnit.name }}</b>
            <span
              class="px-1.5 py-0.5 rounded text-cockpit-xs font-semibold"
              :class="selectedUnit.riskLevel === '高危' ? 'text-rose-400 bg-rose-950/40 border border-rose-500/30' : 'text-amber-400 bg-amber-950/40 border border-amber-500/30'"
            >
              {{ selectedUnit.riskLevel }}
            </span>
          </div>
          <span class="text-cockpit-sm text-slate-400">{{ selectedUnit.province }} · {{ selectedUnit.batch }} · 经办人：{{ selectedUnit.owner }}</span>
          <span class="text-cockpit-xs text-slate-500 mt-1 leading-relaxed">{{ selectedUnit.reason }}</span>
        </div>

        <!-- SHAP Top 3 致险归因标签 -->
        <div class="flex flex-col gap-2">
          <div class="flex items-center justify-between">
            <span class="text-cockpit-sm font-semibold text-slate-300">{{ explanationTitle }}</span>
            <span class="text-cockpit-xs font-mono" :class="isNativeShap ? 'text-sky-400' : 'text-amber-400'">
              {{ isNativeShap ? 'SHAP 贡献 Top 3' : (currentExplanation?.explanationSource === 'RULE_BASED' ? '规则偏离度 Top 3' : '解释不可用') }}
            </span>
          </div>
          <div v-if="loadingExplanation" class="text-cockpit-xs text-slate-500 py-3 text-center">
            正在读取风险解释...
          </div>
          <div v-else-if="currentAttributions.length" class="flex flex-col gap-2">
            <div
              v-for="(attr, idx) in currentAttributions"
              :key="attr.factor"
              class="p-2.5 rounded-lg bg-surface-veil-03 border border-surface-veil-06 flex flex-col gap-1.5"
            >
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-1.5">
                  <span class="font-mono text-cockpit-xs text-slate-400">#{{ idx + 1 }}</span>
                  <b class="text-cockpit-sm text-slate-200">{{ attr.factorName }}</b>
                </div>
                <span class="font-mono text-cockpit-xs font-semibold text-rose-400">
                  {{ attr.weightPct }}%
                </span>
              </div>
              <div class="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                <div
                  class="bg-gradient-to-r from-amber-500 to-rose-500 h-full rounded-full transition-all duration-500"
                  :style="{ width: `${attr.weightPct}%` }"
                />
              </div>
              <p class="text-cockpit-xs text-slate-400 leading-normal">{{ attr.description }}</p>
            </div>
          </div>
          <div v-else class="py-4 text-center text-cockpit-xs text-slate-500">当前没有可验证的风险解释</div>
        </div>

        <!-- 动量特征与客观指标核验 -->
        <div class="flex flex-col gap-2">
          <span class="text-cockpit-sm font-semibold text-slate-300">现场业务动量指标核验</span>
          <div class="grid grid-cols-2 gap-2 text-cockpit-xs">
            <div class="p-2 rounded bg-surface-veil-03 border border-surface-veil-06 flex flex-col gap-0.5">
              <span class="text-slate-400">建设完成度</span>
              <b class="font-mono text-slate-200">{{ selectedUnit.construction }}%</b>
            </div>
            <div class="p-2 rounded bg-surface-veil-03 border border-surface-veil-06 flex flex-col gap-0.5">
              <span class="text-slate-400">双轨核对率</span>
              <b class="font-mono text-slate-200">{{ formatPercent(selectedUnit.voucherRate) }}</b>
            </div>
            <div class="p-2 rounded bg-surface-veil-03 border border-surface-veil-06 flex flex-col gap-0.5">
              <span class="text-slate-400">工期停滞天数</span>
              <b class="font-mono text-amber-400">{{ currentExplanation?.stagnantDays ?? selectedUnit.stagnantDays ?? '—' }}<template v-if="currentExplanation?.stagnantDays != null || selectedUnit.stagnantDays != null"> 天</template></b>
            </div>
            <div class="p-2 rounded bg-surface-veil-03 border border-surface-veil-06 flex flex-col gap-0.5">
              <span class="text-slate-400">近14天推进斜率</span>
              <b class="font-mono text-sky-400">{{ currentExplanation?.progressSlope14d ?? selectedUnit.progressSlope14d ?? '—' }}<template v-if="currentExplanation?.progressSlope14d != null || selectedUnit.progressSlope14d != null">%/天</template></b>
            </div>
            <div class="p-2 rounded bg-surface-veil-03 border border-surface-veil-06 flex flex-col gap-0.5">
              <span class="text-slate-400">培训报错剪刀差</span>
              <b class="font-mono text-rose-400">{{ currentExplanation?.trainingErrorScissors ?? selectedUnit.trainingErrorScissors ?? '—' }}<template v-if="currentExplanation?.trainingErrorScissors != null || selectedUnit.trainingErrorScissors != null">%</template></b>
            </div>
            <div class="p-2 rounded bg-surface-veil-03 border border-surface-veil-06 flex flex-col gap-0.5">
              <span class="text-slate-400">经办人集中度</span>
              <b class="font-mono text-slate-200">{{ currentExplanation?.handlerConcentration != null ? `${Math.round(currentExplanation.handlerConcentration * 100)}%` : (selectedUnit.handlerConcentration != null ? `${Math.round(selectedUnit.handlerConcentration * 100)}%` : '—') }}</b>
            </div>
          </div>
        </div>

        <div class="mt-auto pt-3 border-t border-white/5 text-cockpit-xs text-slate-500 text-center">
          {{ isNativeShap ? 'MySQL HeatWave ML_EXPLAIN_ROW 原生 SHAP · 数据物理不出库' : (currentExplanation?.explanationSource === 'RULE_BASED' ? '基于库内真实特征的确定性规则研判 · 非 SHAP' : '风险解释当前不可用') }}
        </div>
      </aside>
    </div>
  </div>
</template>
