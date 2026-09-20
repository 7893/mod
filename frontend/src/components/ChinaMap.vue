<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { MapChart, ScatterChart, EffectScatterChart } from 'echarts/charts'
import { TooltipComponent, GeoComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import chinaGeoJson from 'china-geojson/src/geojson/china.json'
import {
  cleanProvinceName,
  createChinaMapLegendStops,
  createChinaMapOption,
  createChinaMapScale,
  createChinaMapScatterData,
  type ChinaMapDatum,
} from '../charts/chinaMapOptions.ts'
import type { LiveProjectionEvent } from '../composables/useLiveProjection'
import ChartCanvas from './charts/ChartCanvas.vue'

use([CanvasRenderer, MapChart, ScatterChart, EffectScatterChart, TooltipComponent, GeoComponent])
echarts.registerMap('MOD_CHINA', chinaGeoJson as never)

const props = defineProps<{
  data: ChinaMapDatum[]
  selected?: string
  liveEvent?: LiveProjectionEvent | null
}>()

const emit = defineEmits<{ select: [province: string] }>()

/** 实时事件浮动条 */
const liveBanner = ref<{
  province: string
  unitName: string
  actionDesc: string
} | null>(null)

let bannerTimer: number | null = null

watch(() => props.liveEvent, (ev) => {
  if (!ev || (!ev.province && !ev.unitName)) {
    liveBanner.value = null
    return
  }
  const prov = cleanProvinceName(ev.province)
  const deltaDesc = ev.storyDesc
    ? ev.storyDesc + (ev.amount ? ` (${ev.amount})` : '')
    : '实时业务动态发生'

  liveBanner.value = {
    province: prov,
    unitName: ev.unitName || prov,
    actionDesc: deltaDesc,
  }

  if (bannerTimer !== null) window.clearTimeout(bannerTimer)
  bannerTimer = window.setTimeout(() => {
    liveBanner.value = null
  }, 4500)
}, { immediate: true })

onUnmounted(() => {
  if (bannerTimer !== null) window.clearTimeout(bannerTimer)
})

const scale = computed(() => createChinaMapScale(props.data))
const legendStops = computed(() => createChinaMapLegendStops(scale.value))
const liveScatterData = computed(() => createChinaMapScatterData(props.liveEvent))
const option = computed(() => createChinaMapOption(
  props.data,
  props.selected,
  liveScatterData.value,
  scale.value,
))

function handleClick(params: { name?: string }) {
  if (params?.name) {
    emit('select', params.name)
  }
}
</script>

<template>
  <div class="china-map-container">
    <!-- 实时增量地图跳动提示浮条 (HUD Notification Banner) -->
    <transition
      enter-active-class="map-banner-transition-active"
      leave-active-class="map-banner-transition-active"
      enter-from-class="map-banner-transition-enter-from"
      leave-to-class="map-banner-transition-leave-to"
    >
      <div
        v-if="liveBanner"
        class="map-live-banner"
        @click="liveBanner.province && emit('select', liveBanner.province)"
      >
        <span class="map-live-banner__beacon"></span>
        <span class="map-live-banner__tag">实时动态</span>
        <span class="map-live-banner__province">【{{ liveBanner.province }}】</span>
        <span class="map-live-banner__unit">{{ liveBanner.unitName }}</span>
        <span class="map-live-banner__description">{{ liveBanner.actionDesc }}</span>
      </div>
    </transition>

    <ChartCanvas class="china-map" :option="option" @chart-click="handleClick" />

    <!-- 自绘横向图例：分档色块 + 两端数值 -->
    <div class="map-legend">
      <span class="map-legend__caption">建设完成度</span>
      <span class="map-legend__bound">{{ scale.min }}%</span>
      <div class="map-legend__stops">
        <i
          v-for="stop in legendStops"
          :key="stop.color"
          :style="{ backgroundColor: stop.color }"
          :title="`${stop.from}% – ${stop.to}%`"
        ></i>
      </div>
      <span class="map-legend__bound">{{ scale.max }}%</span>
    </div>
  </div>
</template>
