<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { MapChart, ScatterChart, EffectScatterChart } from 'echarts/charts'
import { TooltipComponent, GeoComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import chinaGeoJson from 'china-geojson/src/geojson/china.json'
import { chartPalette } from '../charts/theme'
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
  const anyEv = ev as any
  let deltaDesc = ''
  if (anyEv.story_desc) {
    deltaDesc = anyEv.story_desc + (anyEv.amount ? ` (${anyEv.amount})` : '')
  } else {
    const bType = anyEv.business_type
    if (bType === 'org_pooled') {
      deltaDesc = '新设单位已登记入库，纳入第八批储备池'
    } else if (bType === 'training_certified') {
      deltaDesc = '关键用户通过机房实操上岗认证考试'
    } else if (bType === 'dual_run_verified') {
      deltaDesc = '完成 1 笔新老系统凭证借贷比对（一致）'
    } else if (ev.increments.vouchers > 0) {
      deltaDesc = `刚刚生成了 ${ev.increments.vouchers} 张会计凭证`
    } else if (ev.increments.documents > 0) {
      deltaDesc = `刚刚入库了 ${ev.increments.documents} 笔业务单据`
    } else if (ev.increments.integrations > 0) {
      deltaDesc = `刚刚完成了 ${ev.increments.integrations} 笔接口集成`
    } else {
      deltaDesc = '实时业务动态发生'
    }
  }

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

/** 散点跳动光圈数据 */
const liveScatterData = computed(() => {
  const ev = props.liveEvent
  if (!ev || !ev.province) return []
  const norm = cleanProvinceName(ev.province)
  const coords = PROVINCE_CENTERS[norm]
  if (!coords) return []

  const anyEv = ev as any
  let actionText = ''
  if (anyEv.story_title) {
    actionText = anyEv.story_title
  } else {
    const bType = anyEv.business_type
    if (bType === 'org_pooled') {
      actionText = '新单位入池'
    } else if (bType === 'training_certified') {
      actionText = '培训认证通过'
    } else if (bType === 'dual_run_verified') {
      actionText = '双轨比对一致'
    } else if (ev.increments.vouchers > 0) {
      actionText = `+${ev.increments.vouchers} 凭证`
    } else if (ev.increments.documents > 0) {
      actionText = `+${ev.increments.documents} 单据`
    } else if (ev.increments.integrations > 0) {
      actionText = `+${ev.increments.integrations} 集成`
    } else {
      actionText = '实时动态'
    }
  }

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
const RAMP = ['#121b2a', '#18273d', '#203657', '#2a4975', '#355c94'] as const
const NO_DATA_COLOR = '#090e17'

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
    trigger: 'item',
    padding: 0,
    borderWidth: 0,
    backgroundColor: 'transparent',
    formatter: (p: any) => {
      if (p.componentType === 'series' && p.seriesType === 'effectScatter') {
        const d = p.data
        return `<div class="map-tip">
          <b>${d.unitName}</b>
          <span style="color:#00f2fe">${d.actionText}</span>
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
          areaColor: isSelected ? '#0284c7' : colorFor(Number(item.value)),
          borderColor: isSelected ? '#38bdf8' : 'rgba(255, 255, 255, 0.12)',
          borderWidth: isSelected ? 2 : 0.8,
        },
        selected: isSelected,
      }
    }),
    itemStyle: { areaColor: NO_DATA_COLOR, borderColor: 'rgba(255, 255, 255, 0.12)', borderWidth: 0.8 },
    emphasis: {
      itemStyle: { areaColor: '#38bdf8', shadowBlur: 16, shadowColor: 'rgba(56, 189, 248, 0.35)' },
      label: { show: true, color: '#070d18', fontWeight: 600 },
    },
    select: {
      itemStyle: { areaColor: '#fbbf24', borderColor: '#fef08a', borderWidth: 1.5 },
      label: { color: '#070d18' },
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
        color: '#00f2fe',
      },
      itemStyle: {
        color: '#00f2fe',
        shadowBlur: 16,
        shadowColor: '#00f2fe',
      },
      label: {
        show: true,
        position: 'top',
        distance: 10,
        formatter: '{b}',
        color: '#ffffff',
        backgroundColor: 'rgba(7, 13, 24, 0.92)',
        borderColor: '#00f2fe',
        borderWidth: 1,
        borderRadius: 4,
        padding: [4, 8],
        fontSize: 11,
        fontWeight: 'bold',
        shadowBlur: 10,
        shadowColor: 'rgba(0, 242, 254, 0.5)',
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

<style scoped>
.china-map-container {
  position: relative;
  width: 100%;
  height: 100%;
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
  background: rgba(7, 18, 36, 0.94);
  border: 1px solid rgba(0, 242, 254, 0.7);
  box-shadow: 0 0 20px rgba(0, 242, 254, 0.35), 0 4px 16px rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(8px);
  cursor: pointer;
  white-space: nowrap;
  pointer-events: auto;
}

.map-live-banner:hover {
  border-color: #00f2fe;
  box-shadow: 0 0 24px rgba(0, 242, 254, 0.55), 0 4px 16px rgba(0, 0, 0, 0.7);
}

.banner-pulse-beacon {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #00f2fe;
  box-shadow: 0 0 10px #00f2fe;
  animation: banner-beacon-ping 1.4s infinite;
  flex-shrink: 0;
}

@keyframes banner-beacon-ping {
  0% { transform: scale(0.85); opacity: 1; }
  50% { transform: scale(1.6); opacity: 0.5; }
  100% { transform: scale(0.85); opacity: 1; }
}

.banner-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  background: rgba(0, 242, 254, 0.2);
  color: #00f2fe;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.banner-prov {
  font-size: 12px;
  font-weight: 700;
  color: #38bdf8;
}

.banner-unit {
  font-size: 12px;
  font-weight: 600;
  color: #ffffff;
}

.banner-desc {
  font-size: 12px;
  color: #34d399;
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
</style>
