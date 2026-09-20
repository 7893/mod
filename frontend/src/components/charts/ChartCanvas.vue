<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import VChart from 'vue-echarts'
import EmptyNote from '../blocks/EmptyNote.vue'

defineOptions({ inheritAttrs: false })

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
  <EmptyNote v-if="error" v-bind="$attrs">{{ error }}</EmptyNote>
  <EmptyNote v-else-if="loading" v-bind="$attrs">数据加载中</EmptyNote>
  <EmptyNote v-else-if="empty || !option" v-bind="$attrs">{{ emptyText }}</EmptyNote>
  <VChart
    v-else
    v-bind="$attrs"
    class="w-full h-full min-h-0"
    :option="option"
    autoresize
    @click="emit('chartClick', $event)"
  />
</template>
