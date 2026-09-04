<script setup lang="ts">
import MetricGrid from './MetricGrid.vue'
import type { MetricItem } from './types.ts'

withDefaults(
  defineProps<{
    /** 图表旁的说明指标，横排一行。 */
    stats?: MetricItem[]
    statsPosition?: 'top' | 'bottom'
    /** 图表下方的口径注脚。 */
    footnote?: string
  }>(),
  { statsPosition: 'top' },
)
</script>

<template>
  <div class="chart-block">
    <MetricGrid
      v-if="stats?.length && statsPosition === 'top'"
      class="chart-block__stats"
      :items="stats"
      variant="inline"
      size="sm"
      :columns="stats.length"
    />

    <!-- 图表容器只声明「吃满剩余高度」，绝不写死像素高度：
         写死高度会在容器变矮时撑破父级，坐标轴被裁掉。 -->
    <div class="chart-block__canvas">
      <slot />
    </div>

    <MetricGrid
      v-if="stats?.length && statsPosition === 'bottom'"
      class="chart-block__stats"
      :items="stats"
      variant="inline"
      size="sm"
      :columns="stats.length"
    />

    <p v-if="footnote" class="chart-block__note">{{ footnote }}</p>
  </div>
</template>
