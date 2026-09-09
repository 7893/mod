<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import {
  calmAnimation,
  categoryAxis,
  chartInk,
  chartPalette,
  chartTooltip,
  valueAxis,
} from '../charts/theme.ts'
import type { TrendItem } from '../stores/project.ts'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent])

const props = defineProps<{
  data: TrendItem[]
}>()

// 对称时间窗：若传入数据超过7个节点，以今日为中心截取前后各半（7节点）；若不足或恰好7节点则直接展示 (KI-065)
const displayData = computed(() => {
  const list = props.data || []
  if (list.length <= 7) return list

  const now = new Date()
  const mm = String(now.getMonth() + 1).padStart(2, '0')
  const dd = String(now.getDate()).padStart(2, '0')
  const todayDate = `${mm}-${dd}`
  const todayFullDate = `${now.getFullYear()}-${todayDate}`

  let centerIdx = list.findIndex(
    (item) => item.fullDate === todayFullDate || item.date === todayDate,
  )
  if (centerIdx === -1) {
    centerIdx = Math.floor(list.length / 2)
  }
  const start = Math.max(0, Math.min(centerIdx - 3, list.length - 7))
  return list.slice(start, start + 7)
})

const trendOption = computed(() => {
  const list = displayData.value
  return {
    ...calmAnimation,
    tooltip: { trigger: 'axis', ...chartTooltip },
    grid: { top: 6, bottom: 22, left: 38, right: 12 },
    xAxis: {
      ...categoryAxis,
      data: list.map((v) => v.date),
      boundaryGap: false,
      axisLabel: { color: chartInk.textDim, fontSize: 10, fontFamily: 'monospace' },
    },
    yAxis: {
      ...valueAxis,
      min: 0,
      splitNumber: 3,
      axisLabel: { color: chartInk.textDim, fontSize: 10, fontFamily: 'monospace' },
      splitLine: { lineStyle: { color: chartInk.borderSoft, type: 'dashed' } },
    },
    series: [
      {
        name: '正式上线',
        type: 'line',
        smooth: true,
        data: list.map((v) => v.launched),
        showSymbol: false,
        lineStyle: { color: chartPalette.accent, width: 2.2 },
      },
      {
        name: '双轨核对',
        type: 'bar',
        barMaxWidth: 18,
        data: list.map((v) => v.dual ?? 0),
        itemStyle: { color: chartPalette.warning, borderRadius: [3, 3, 0, 0], opacity: 0.82 },
      },
    ],
  }
})
</script>

<template>
  <div class="w-full h-full flex flex-col min-h-0">
    <VChart class="w-full h-full flex-1" :option="trendOption" autoresize />
  </div>
</template>
