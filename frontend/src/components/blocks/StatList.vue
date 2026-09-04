<script setup lang="ts">
import type { StatRow } from './types.ts'

withDefaults(
  defineProps<{
    rows: StatRow[]
    /** 行内是否显示排名徽标（取 row.rank，缺省用下标）。 */
    ranked?: boolean
    /** 行高档位。dense 用于 8 条以上的长列表。 */
    density?: 'dense' | 'normal'
    /** 超出高度时是否允许滚动，否则等分压缩。 */
    scroll?: boolean
  }>(),
  { ranked: false, density: 'normal', scroll: false },
)

function clamp(n: number | undefined) {
  return Math.min(100, Math.max(0, n ?? 0))
}
</script>

<template>
  <div class="stat-list" :class="[`stat-list--${density}`, { 'stat-list--scroll': scroll }]">
    <div
      v-for="(row, idx) in rows"
      :key="row.id ?? row.label"
      class="stat-row"
      :class="`is-${row.tone || 'default'}`"
    >
      <span v-if="ranked" class="stat-row__rank">{{ row.rank ?? idx + 1 }}</span>
      <component :is="row.icon" v-if="row.icon" :size="15" class="stat-row__icon" />

      <div class="stat-row__main">
        <div class="stat-row__head">
          <span class="stat-row__label">{{ row.label }}</span>
          <span v-if="row.value !== undefined" class="stat-row__value">
            {{ row.value }}<small v-if="row.unit">{{ row.unit }}</small>
          </span>
        </div>

        <span v-if="row.sub" class="stat-row__sub">{{ row.sub }}</span>

        <div v-if="row.progress !== undefined" class="stat-row__bars">
          <div class="stat-row__track" :title="row.progressLabel">
            <div class="stat-row__fill" :style="{ width: `${clamp(row.progress)}%` }"></div>
          </div>
          <div v-if="row.progressAlt !== undefined" class="stat-row__track" :title="row.progressAltLabel">
            <div class="stat-row__fill is-alt" :style="{ width: `${clamp(row.progressAlt)}%` }"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
