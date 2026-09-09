<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { MapChart, ScatterChart, EffectScatterChart } from 'echarts/charts'
import { TooltipComponent, GeoComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import chinaGeoJson from 'china-geojson/src/geojson/china.json'
import { chartInk, chartPalette, mapRamp } from '../charts/theme'
import type { LiveProjectionEvent } from '../composables/useLiveProjection'

use([CanvasRenderer, MapChart, ScatterChart, EffectScatterChart, TooltipComponent, GeoComponent])
echarts.registerMap('MOD_CHINA', chinaGeoJson as never)

const props = defineProps<{
  data: Array<{
    name: string
    value: number
    total: number
    launched: number
    dual: number
    constructionPct?: number
    todayAdded?: number
    docsTodayAdded?: number
    docsAddedAsOfDate?: string
    addedAsOfDate?: string
  }>
  selected?: string
  liveEvent?: LiveProjectionEvent | null
}>()

const emit = defineEmits<{ select: [province: string] }>()

const PROVINCE_CENTERS: Record<string, [number, number]> = {
  '北京': [116.405, 39.905],
  '天津': [117.190, 39.126],
  '河北': [114.502, 38.045],
  '山西': [112.549, 37.857],
  '内蒙古': [111.671, 40.818],
  '辽宁': [123.429, 41.797],
  '吉林': [125.325, 43.887],
  '黑龙江': [126.642, 45.757],
  '上海': [121.473, 31.232],
  '江苏': [118.767, 32.042],
  '浙江': [120.154, 30.287],
  '安徽': [117.283, 31.861],
  '福建': [119.306, 26.075],
  '江西': [115.892, 28.676],
  '山东': [117.001, 36.676],
  '河南': [113.665, 34.758],
  '湖北': [114.299, 30.584],
  '湖南': [112.982, 28.194],
  '广东': [113.281, 23.125],
  '广西': [108.320, 22.824],
  '海南': [110.331, 20.032],
  '重庆': [106.505, 29.533],
  '四川': [104.066, 30.659],
  '贵州': [106.713, 26.578],
  '云南': [102.712, 25.041],
  '西藏': [91.132, 29.660],
  '陕西': [108.948, 34.263],
  '甘肃': [103.824, 36.058],
  '青海': [101.779, 36.623],
  '宁夏': [106.278, 38.466],
  '新疆': [87.618, 43.793],
  '香港': [114.173, 22.320],
  '澳门': [113.549, 22.199],
  '台湾': [121.509, 25.044],
}

function cleanProvinceName(raw?: string): string {
  if (!raw) return ''
  return raw.replace(/(省|市|自治区|壮族|回族|维吾尔|特别行政区)/g, '').trim()
}

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

/** 散点跳动光圈数据 */
const liveScatterData = computed(() => {
  const ev = props.liveEvent
  if (!ev || !ev.province) return []
  const norm = cleanProvinceName(ev.province)
  const coords = PROVINCE_CENTERS[norm]
  if (!coords) return []

  const actionText = ev.storyTitle || '实时动态'

  const labelText = `${ev.unitName || norm} · ${actionText}`

  return [
    {
      name: labelText,
      value: [coords[0], coords[1], 100],
      unitName: ev.unitName || norm,
      province: norm,
      actionText,
    },
  ]
})

/**
 * 建设完成度色带：从深邃碳素冷灰蓝渐变到沉稳星际群青 (低 → 高)
 */
const RAMP = mapRamp.steps
const NO_DATA_COLOR = mapRamp.noData

const scale = computed(() => {
  const values = props.data.map((item) => Number(item.value)).filter(Number.isFinite)
  const dataMin = values.length ? Math.min(...values) : 0
  const dataMax = values.length ? Math.max(...values) : 100
  const padding = Math.max(2, (dataMax - dataMin) * 0.12)
  return {
    min: Math.max(0, Math.floor(dataMin - padding)),
    max: Math.min(100, Math.ceil(dataMax + padding)),
  }
})

const colorFor = (value: number) => {
  const { min, max } = scale.value
  if (!Number.isFinite(value)) return NO_DATA_COLOR
  const ratio = max === min ? 0 : (value - min) / (max - min)
  const index = Math.min(RAMP.length - 1, Math.max(0, Math.round(ratio * (RAMP.length - 1))))
  return RAMP[index]
}

const legendStops = computed(() => {
  const { min, max } = scale.value
  const step = (max - min) / RAMP.length
  return RAMP.map((color, index) => ({
    color,
    from: Math.round(min + step * index),
    to: Math.round(min + step * (index + 1)),
  }))
})

const option = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: {
    confine: true,
    trigger: 'item',
    padding: 0,
    borderWidth: 0,
    backgroundColor: 'transparent',
    formatter: (p: any) => {
      if (p.componentType === 'series' && p.seriesType === 'effectScatter') {
        const d = p.data
        return `<div class="map-tip">
          <b>${d.unitName}</b>
          <span style="color:${chartPalette.accent}">${d.actionText}</span>
          <i>所属省份：${d.province}</i>
        </div>`
      }
      const item = props.data.find((v) => v.name === p.name)
      if (!item) return `<div class="map-tip"><b>${p.name}</b><span>暂无纳管单位</span></div>`
      return `<div class="map-tip">
        <b>${p.name}</b>
        <span>建设完成度 ${item.value || item.constructionPct || 0}%</span>
        <i>纳管 ${item.total} 家 · 上线 ${item.launched} 家 · 双轨 ${item.dual} 家</i>
      </div>`
    },
  },
  // 基础地图底图
  geo: {
    map: 'MOD_CHINA',
    roam: false,
    zoom: 1.2,
    top: 8,
    bottom: 34,
    left: 8,
    right: 8,
    regions: props.data.map((item) => {
      const isSelected = !!(props.selected && props.selected !== '全国' && props.selected === item.name)
      return {
        name: item.name,
        itemStyle: {
          areaColor: isSelected ? chartPalette.accentDim : colorFor(Number(item.value)),
          borderColor: isSelected ? chartPalette.accent : chartInk.border,
          borderWidth: isSelected ? 2 : 0.8,
        },
        selected: isSelected,
      }
    }),
    itemStyle: { areaColor: NO_DATA_COLOR, borderColor: chartInk.border, borderWidth: 0.8 },
    emphasis: {
      itemStyle: { areaColor: chartPalette.accent },
      label: { show: true, color: chartInk.onAccent, fontWeight: 600 },
    },
    select: {
      itemStyle: { areaColor: chartPalette.warning, borderColor: chartPalette.warning, borderWidth: 1.5 },
      label: { color: chartInk.onAccent },
    },
    selectedMode: 'single' as const,
    label: { show: false },
  },
  series: [
    // 实时跳动光圈 (EffectScatter)
    {
      type: 'effectScatter',
      coordinateSystem: 'geo',
      data: liveScatterData.value,
      symbolSize: 14,
      rippleEffect: {
        scale: 6,
        period: 2.2,
        brushType: 'stroke',
        color: chartPalette.accent,
      },
      itemStyle: { color: chartPalette.accent },
      label: {
        show: true,
        position: 'top',
        distance: 10,
        formatter: '{b}',
        color: chartInk.textPrimary,
        backgroundColor: chartInk.bgTooltip,
        borderColor: chartPalette.accent,
        borderWidth: 1,
        borderRadius: 4,
        padding: [4, 8],
        fontSize: 11,
        fontWeight: 'bold',
      },
      zlevel: 10,
    },
  ],
}))

function handleClick(params: any) {
  if (params?.name) {
    emit('select', params.name)
  }
}
</script>

<template>
  <div class="china-map-container">
    <!-- 实时增量地图跳动提示浮条 (HUD Notification Banner) -->
    <transition name="map-banner-pop">
      <div
        v-if="liveBanner"
        class="map-live-banner"
        @click="liveBanner.province && emit('select', liveBanner.province)"
      >
        <span class="banner-pulse-beacon"></span>
        <span class="banner-tag">实时动态</span>
        <span class="banner-prov">【{{ liveBanner.province }}】</span>
        <span class="banner-unit">{{ liveBanner.unitName }}</span>
        <span class="banner-desc">{{ liveBanner.actionDesc }}</span>
      </div>
    </transition>

    <VChart class="china-map" :option="option" autoresize @click="handleClick" />

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

<style>
@reference "../styles.css";

/* ECharts tooltip 渲染在组件根之外，须为全局规则 */
.map-tip {
  background: color-mix(in srgb, var(--color-slate-900) 95%, transparent);
  border: 1px solid var(--color-surface-hairline);
  border-radius: var(--radius-md);
  padding: --spacing(3) --spacing(4);
  min-width: 180px;
  box-shadow: 0 8px 24px rgb(0 0 0 / 40%);
}

.map-tip b {
  display: block;
  font-size: var(--text-cockpit-lg);
  color: var(--color-slate-50);
  margin-bottom: --spacing(1);
}

.map-tip span {
  display: block;
  font-size: var(--text-cockpit-md);
  color: var(--color-slate-400);
  margin-bottom: --spacing(1);
}

.map-tip i {
  display: block;
  font-style: normal;
  font-size: var(--text-cockpit-sm);
  color: var(--color-slate-500);
}
</style>

<style scoped>
@reference "../styles.css";

.china-map-container {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 0;
}

.china-map {
  width: 100%;
  height: 100%;
}

/* 实时业务动态浮动条 (HUD Banner) */
.map-live-banner {
  position: absolute;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  border-radius: 20px;
  background: color-mix(in srgb, var(--color-surface-base) 94%, transparent);
  border: 1px solid color-mix(in srgb, var(--color-sky-400) 70%, transparent);
  box-shadow: 0 4px 16px rgb(0 0 0 / 60%);
  backdrop-filter: blur(8px);
  cursor: pointer;
  white-space: nowrap;
  pointer-events: auto;
}

.map-live-banner:hover {
  border-color: var(--color-sky-400);
  box-shadow: 0 4px 16px rgb(0 0 0 / 70%);
}

.banner-pulse-beacon {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-sky-400);
  animation: banner-beacon-ping 1.4s infinite;
  flex-shrink: 0;
}

@keyframes banner-beacon-ping {
  0% { transform: scale(0.85); opacity: 1; }
  50% { transform: scale(1.6); opacity: 0.5; }
  100% { transform: scale(0.85); opacity: 1; }
}

.banner-tag {
  font-size: var(--text-cockpit-xs);
  padding: 1px 6px;
  border-radius: 3px;
  background: color-mix(in srgb, var(--color-sky-400) 20%, transparent);
  color: var(--color-sky-400);
  font-weight: 700;
  letter-spacing: 0.5px;
}

.banner-prov {
  font-size: var(--text-cockpit-sm);
  font-weight: 700;
  color: var(--color-sky-400);
}

.banner-unit {
  font-size: var(--text-cockpit-sm);
  font-weight: 600;
  color: var(--color-white);
}

.banner-desc {
  font-size: var(--text-cockpit-sm);
  color: var(--color-emerald-400);
  font-weight: 600;
}

.map-banner-pop-enter-active,
.map-banner-pop-leave-active {
  transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}

.map-banner-pop-enter-from {
  opacity: 0;
  transform: translate(-50%, -18px) scale(0.92);
}

.map-banner-pop-leave-to {
  opacity: 0;
  transform: translate(-50%, -12px) scale(0.96);
}

/* 自绘横向图例，停靠左下角；固定一行 flex，避免 visualMap 横向模式渲染成竖块 */
.map-legend {
  position: absolute;
  left: --spacing(3);
  bottom: --spacing(2);
  z-index: 5;
  display: flex;
  align-items: center;
  gap: --spacing(2);
  padding: 5px --spacing(3);
  background: color-mix(in srgb, var(--color-surface-base) 72%, transparent);
  border: 1px solid var(--color-surface-veil-03);
  border-radius: 999px;
  pointer-events: none;
}

.map-legend__caption {
  font-size: var(--text-cockpit-xs);
  color: var(--color-slate-500);
  white-space: nowrap;
}

.map-legend__bound {
  font-family: var(--font-mono);
  font-size: var(--text-cockpit-xs);
  color: var(--color-slate-600);
  white-space: nowrap;
}

.map-legend__stops {
  display: flex;
  align-items: center;
  gap: 2px;
}

.map-legend__stops i {
  display: block;
  width: 20px;
  height: 6px;
  border-radius: 1px;
}
</style>
