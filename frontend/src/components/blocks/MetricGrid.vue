<script setup lang="ts">
import { computed } from 'vue'
import { balancedColumns } from '../../layout/grid.ts'
import type { MetricItem } from './types.ts'

const props = withDefaults(
  defineProps<{
    items: MetricItem[]
    /**
     * inline：图标在左、文字在右，一行一条，适合 3–4 项的窄栏。
     * stacked：标签在上、数值在下，适合并排多列或需要进度条/注脚的场景。
     */
    variant?: 'inline' | 'stacked'
    /** 数值字号档位。 */
    size?: 'sm' | 'md' | 'lg'
    /** 单行最多几列；实际列数由 balancedColumns 按项数取整除值。 */
    maxPerRow?: number
    /** 固定列数，给了就不再自动推导（如强制 2×2）。 */
    columns?: number
    /** 卡片是否平分容器高度。列表型区块给 true，页首指标带给 false。 */
    fill?: boolean
  }>(),
  { variant: 'stacked', size: 'md', maxPerRow: 4, fill: false },
)

const gridStyle = computed(() => ({
  gridTemplateColumns: `repeat(${props.columns ?? balancedColumns(props.items.length, props.maxPerRow)}, minmax(0, 1fr))`,
}))
</script>

<template>
  <div
    class="metric-grid"
    :class="[`metric-grid--${variant}`, `metric-grid--${size}`, { 'metric-grid--fill': fill }]"
    :style="gridStyle"
  >
    <div
      v-for="(item, idx) in items"
      :key="item.label + idx"
      class="metric-cell"
      :class="`is-${item.tone || 'default'}`"
    >
      <component :is="item.icon" v-if="item.icon" :size="18" class="metric-cell__icon" />

      <div class="metric-cell__body">
        <span class="metric-cell__label">{{ item.label }}</span>
        <b class="metric-cell__value">
          {{ item.value }}<small v-if="item.unit">{{ item.unit }}</small>
        </b>

        <div v-if="item.progress !== undefined" class="metric-cell__track">
          <div class="metric-cell__fill" :style="{ width: `${Math.min(100, Math.max(0, item.progress))}%` }"></div>
        </div>

        <div v-if="item.meta?.length" class="metric-cell__meta">
          <span v-for="m in item.meta" :key="m.label">{{ m.label }} {{ m.value }}</span>
        </div>

        <span v-if="item.hint" class="metric-cell__hint">{{ item.hint }}</span>
      </div>
    </div>
  </div>
</template>
