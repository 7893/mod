<script setup lang="ts">
import MetricGrid from './MetricGrid.vue'
import type { MetricItem } from './types.ts'

/**
 * 各屏首行「指挥带」骨架：左侧领域主图 + 右侧少量精确事实。
 * 右栏默认用平铺 MetricGrid 渲染 facts；结构特殊的屏用 #aside 插槽自定义。
 */
withDefaults(
  defineProps<{
    /** 主图占 12 栅格中的几列。 */
    chartSpan?: number
    facts?: MetricItem[]
    factColumns?: number
  }>(),
  { chartSpan: 9 },
)

function span(n: number) {
  return { gridColumn: `span ${n} / span ${n}` }
}
</script>

<template>
  <div class="grid grid-cols-12 gap-3 h-24 min-h-0">
    <section class="flex flex-col pr-3 border-r border-surface-veil-06 min-h-0" :style="span(chartSpan)">
      <slot name="chart" />
    </section>
    <section class="flex flex-col min-h-0" :style="span(12 - chartSpan)">
      <slot name="aside">
        <MetricGrid v-if="facts?.length" :items="facts" flat fill size="xs" :columns="factColumns" />
      </slot>
    </section>
  </div>
</template>
