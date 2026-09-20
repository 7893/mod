<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { createOverviewTrendOption } from '../charts/overviewTrendOptions.ts'
import type { TrendItem } from '../stores/project.ts'
import ChartCanvas from './charts/ChartCanvas.vue'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent])

const props = defineProps<{
  data: TrendItem[]
}>()

const trendOption = computed(() => createOverviewTrendOption(props.data))
</script>

<template>
  <ChartCanvas
    :option="trendOption"
    :empty="data.length === 0"
    empty-text="暂无趋势数据"
  />
</template>
