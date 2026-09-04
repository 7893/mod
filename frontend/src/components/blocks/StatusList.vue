<script setup lang="ts">
import { ChevronRight } from 'lucide-vue-next'
import type { StatusRow } from './types.ts'

withDefaults(
  defineProps<{
    rows: StatusRow[]
    /** 行末是否显示指向箭头（用于可跳转的列表）。 */
    chevron?: boolean
    /** 超出高度时滚动，否则各行等分压缩。 */
    scroll?: boolean
  }>(),
  { chevron: false, scroll: false },
)

const emit = defineEmits<{ (e: 'select', row: StatusRow): void }>()
</script>

<template>
  <div class="status-list" :class="{ 'status-list--scroll': scroll }">
    <component
      :is="row.href ? 'a' : 'div'"
      v-for="(row, idx) in rows"
      :key="row.id ?? idx"
      class="status-row"
      :class="[`is-${row.tone || 'default'}`, { 'is-interactive': row.href || chevron }]"
      :href="row.href"
      @click="!row.href && emit('select', row)"
    >
      <span v-if="row.dot" class="status-row__dot"></span>
      <component :is="row.icon" v-else-if="row.icon" :size="16" class="status-row__icon" />

      <div class="status-row__body">
        <b class="status-row__title">{{ row.title }}</b>
        <p v-if="row.desc" class="status-row__desc">{{ row.desc }}</p>
      </div>

      <ChevronRight v-if="chevron" :size="14" class="status-row__chevron" />
    </component>
  </div>
</template>
