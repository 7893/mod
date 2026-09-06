<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import {
  calmAnimation,
  categoryAxis,
  chartTooltip,
  valueAxis,
} from '../charts/theme.ts'
import type { TrendItem } from '../stores/project.ts'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

const props = defineProps<{
  data: TrendItem[]
}>()

const trendOption = computed(() => ({
  ...calmAnimation,
  tooltip: { trigger: 'axis', ...chartTooltip },
  grid: { top: 22, bottom: 22, left: 38, right: 12 },
  legend: {
    show: true,
    right: 8,
    top: 0,
    itemWidth: 10,
    itemHeight: 3,
    textStyle: { color: '#94a3b8', fontSize: 10 },
  },
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
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(56, 189, 248, 0.32)' },
            { offset: 1, color: 'rgba(56, 189, 248, 0.01)' },
          ],
        },
      },
    },
    {
      name: '双轨核对',
      type: 'line',
      smooth: true,
      data: props.data.map((v) => v.dual ?? 0),
      showSymbol: false,
      lineStyle: { color: '#fbbf24', width: 2, type: [4, 4] },
    },
  ],
}))
</script>

<template>
  <div class="w-full h-full flex flex-col min-h-0">
    <VChart class="w-full h-full flex-1" :option="trendOption" autoresize />
  </div>
</template>
