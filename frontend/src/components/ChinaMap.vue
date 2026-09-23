<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { MapChart, ScatterChart, EffectScatterChart } from 'echarts/charts'
import { TooltipComponent, GeoComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import {
  cleanProvinceName,
  createChinaMapLegendStops,
  createChinaMapOption,
  createChinaMapScale,
  createChinaMapScatterData,
  type ChinaMapDatum,
} from '../charts/chinaMapOptions.ts'
import { fetchChinaMapGeoJson } from '../charts/chinaMapSource.ts'
import type { LiveProjectionEvent } from '../composables/useLiveProjection'
import {
  hasProvinceMultiSelectModifier,
  type ProvinceSelectionModifierEvent,
} from '../utils/provinceSelection.ts'
import ChartCanvas from './charts/ChartCanvas.vue'

use([CanvasRenderer, MapChart, ScatterChart, EffectScatterChart, TooltipComponent, GeoComponent])

type MapSourceStatus = 'loading' | 'ready' | 'unconfigured' | 'error'

const mapSourceUrl = import.meta.env.VITE_CHINA_MAP_GEOJSON_URL?.trim() ?? ''
const mapSourceStatus = ref<MapSourceStatus>(mapSourceUrl ? 'loading' : 'unconfigured')
const mapSourceController = new AbortController()

const mapSourceError = computed(() => {
  if (mapSourceStatus.value === 'unconfigured') {
    return '未配置合规地图数据源；请由部署方设置 VITE_CHINA_MAP_GEOJSON_URL'
  }
  if (mapSourceStatus.value === 'error') {
    return '地图数据源不可用；请检查部署方配置、CORS 与 GeoJSON 格式'
  }
  return null
})

onMounted(async () => {
  if (!mapSourceUrl) return
  try {
    const geometry = await fetchChinaMapGeoJson(mapSourceUrl, mapSourceController.signal)
    echarts.registerMap('MOD_CHINA', geometry as never)
    mapSourceStatus.value = 'ready'
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') return
    mapSourceStatus.value = 'error'
  }
})

const props = defineProps<{
  data: ChinaMapDatum[]
  selected?: readonly string[]
  liveEvent?: LiveProjectionEvent | null
}>()

const emit = defineEmits<{ select: [province: string, additive: boolean] }>()

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
  mapSourceController.abort()
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

interface MapClickParams {
  name?: string
  seriesType?: string
  data?: { province?: string }
  event?: ProvinceSelectionModifierEvent
}

function handleClick(params: MapClickParams) {
  const province = params.seriesType === 'effectScatter' ? params.data?.province : params.name
  if (!province) return
  emit('select', province, hasProvinceMultiSelectModifier(params.event))
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
        v-if="mapSourceStatus === 'ready' && liveBanner"
        class="map-live-banner"
        @click="liveBanner.province && emit('select', liveBanner.province, false)"
      >
        <span class="map-live-banner__beacon"></span>
        <span class="map-live-banner__tag">实时动态</span>
        <span class="map-live-banner__province">【{{ liveBanner.province }}】</span>
        <span class="map-live-banner__unit">{{ liveBanner.unitName }}</span>
        <span class="map-live-banner__description">{{ liveBanner.actionDesc }}</span>
      </div>
    </transition>

    <ChartCanvas
      class="china-map"
      :option="mapSourceStatus === 'ready' ? option : null"
      :loading="mapSourceStatus === 'loading'"
      :error="mapSourceError"
      :update-options="{ replaceMerge: ['geo'] }"
      @chart-click="handleClick"
    />

    <!-- 自绘横向图例：分档色块 + 两端数值 -->
    <div v-if="mapSourceStatus === 'ready'" class="map-legend">
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
