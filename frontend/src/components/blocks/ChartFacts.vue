<script setup lang="ts">
withDefaults(defineProps<{
  variant?: 'chart-led' | 'facts-led'
}>(), { variant: 'chart-led' })
</script>

<template>
  <div class="chart-facts" :class="`chart-facts--${variant}`">
    <div class="chart-facts__chart"><slot name="chart" /></div>
    <div class="chart-facts__facts"><slot name="facts" /></div>
  </div>
</template>
