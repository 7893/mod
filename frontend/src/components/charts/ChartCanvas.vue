<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import VChart from 'vue-echarts'
import EmptyNote from '../blocks/EmptyNote.vue'

const emit = defineEmits<{
  chartClick: [params: { name?: string }]
}>()

withDefaults(defineProps<{
  option?: EChartsOption | null
  loading?: boolean
  error?: string | null
  empty?: boolean
  emptyText?: string
}>(), {
  option: null,
  error: null,
  emptyText: '暂无数据',
})
</script>

<template>
  <div class="w-full h-full min-h-0">
    <EmptyNote v-if="error">{{ error }}</EmptyNote>
    <EmptyNote v-else-if="loading">数据加载中</EmptyNote>
    <EmptyNote v-else-if="empty || !option">{{ emptyText }}</EmptyNote>
    <VChart
      v-else
      class="w-full h-full min-h-0"
      :option="option"
      autoresize
      @click="emit('chartClick', $event)"
    />
  </div>
</template>
