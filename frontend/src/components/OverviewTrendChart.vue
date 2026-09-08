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
  chartTooltip,
  valueAxis,
} from '../charts/theme.ts'
import type { TrendItem } from '../stores/project.ts'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent])

const props = defineProps<{
  data: TrendItem[]
}>()

const trendOption = computed(() => ({
  ...calmAnimation,
  tooltip: { trigger: 'axis', ...chartTooltip },
  grid: { top: 6, bottom: 22, left: 38, right: 12 },
  xAxis: {
    ...categoryAxis,
    data: props.data.map((v) => v.date),
    boundaryGap: false,
    axisLabel: { color: '#64748b', fontSize: 10, fontFamily: 'monospace' },
    axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.08)' } },
  },
  yAxis: {
    ...valueAxis,
    min: 0,
    splitNumber: 3,
    axisLabel: { color: '#64748b', fontSize: 10, fontFamily: 'monospace' },
    splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)', type: 'dashed' } },
  },
  series: [
    {
      name: '正式上线',
      type: 'line',
      smooth: true,
      data: props.data.map((v) => v.launched),
      showSymbol: false,
      lineStyle: { color: '#38bdf8', width: 2.2 },
    },
    {
      name: '双轨核对',
      type: 'bar',
      barMaxWidth: 18,
      data: props.data.map((v) => v.dual ?? 0),
      itemStyle: { color: '#fbbf24', borderRadius: [3, 3, 0, 0], opacity: 0.82 },
    },
  ],
}))
</script>

<template>
  <div class="w-full h-full flex flex-col min-h-0">
    <VChart class="w-full h-full flex-1" :option="trendOption" autoresize />
  </div>
</template>
