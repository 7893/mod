<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  Activity,
  AlertTriangle,
  BarChart3,
  ClipboardCheck,
  Fullscreen,
  Hammer,
  LayoutDashboard,
  Minimize,
  RefreshCw,
  Rocket,
  WifiOff,
} from 'lucide-vue-next'
import { useProjectStore } from './stores/project.ts'
import { useScaleScreen } from './composables/useScaleScreen.ts'

const route = useRoute()
const store = useProjectStore()
const now = ref(new Date())
let timer = 0

// 全站统一缩放骨架：导航始终保留，内容画布固定以 1920×980 为设计基准。
const { scale, viewportRef, baseWidth, baseHeight } = useScaleScreen({
  baseWidth: 1920,
  baseHeight: 980,
})

const formattedClock = computed(() => {
  const formatter = new Intl.DateTimeFormat('zh-CN', {
    timeZone: store.snapshot.meta.displayTimezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
  const parts = formatter.formatToParts(now.value)
  const map: Record<string, string> = {}
  parts.forEach((p) => { map[p.type] = p.value })
  return `${map.year}-${map.month}-${map.day} ${map.hour}:${map.minute}:${map.second}`
})

const isFullscreen = ref(false)

const syncFullscreenState = () => {
  isFullscreen.value = !!document.fullscreenElement
}

const toggleFullscreen = async () => {
  if (!document.fullscreenElement) {
    await document.documentElement.requestFullscreen()
  } else {
    await document.exitFullscreen()
  }
}

// 同步 isFullscreen 状态（ESC 退出也能感知）
onMounted(() => {
  syncFullscreenState()
  document.addEventListener('fullscreenchange', syncFullscreenState)
})

const handleManualRefresh = () => {
  void store.refresh(false)
}

const leftNavItems = [
  { path: '/a', label: '项目总览', icon: LayoutDashboard },
  { path: '/b', label: '建设进度', icon: Hammer },
  { path: '/c', label: '上线推广', icon: Rocket },
]

const rightNavItems = [
  { path: '/d', label: '业务运营', icon: BarChart3 },
  { path: '/e', label: '合规监督', icon: ClipboardCheck },
  { path: '/f', label: '风险预警', icon: AlertTriangle },
]

const isActive = (path: string) => {
  if (path === '/a') return route.path === '/' || route.path === '/a'
  return route.path === path
}

onMounted(() => {
  now.value = new Date()
  timer = window.setInterval(() => { now.value = new Date() }, 1000)
})

onBeforeUnmount(() => {
  window.clearInterval(timer)
  document.removeEventListener('fullscreenchange', syncFullscreenState)
})
</script>

<template>
  <div class="command-shell">
    <!-- 顶部导航栏：全屏模式也必须保留，保证六屏之间始终可切换 -->
    <header class="command-header">
      <!-- 左侧：前三个菜单 -->
      <div class="header-left">
        <nav class="header-nav">
          <RouterLink
            v-for="item in leftNavItems"
            :key="item.path"
            :to="item.path"
            class="nav-tab"
            :class="{ active: isActive(item.path) }"
          >
            <component :is="item.icon" :size="16" />
            <span>{{ item.label }}</span>
          </RouterLink>
        </nav>
      </div>

      <!-- 中央：大屏主标题 -->
      <div class="header-center">
        <h1 class="header-main-title">业务系统建设推广大屏</h1>
        <div class="header-title-decor"></div>
      </div>

      <!-- 右侧：后三个菜单 + 状态控制 -->
      <div class="header-right">
        <nav class="header-nav">
          <RouterLink
            v-for="item in rightNavItems"
            :key="item.path"
            :to="item.path"
            class="nav-tab"
            :class="{ active: isActive(item.path) }"
          >
            <component :is="item.icon" :size="16" />
            <span>{{ item.label }}</span>
            <i
              v-if="item.path === '/f' && store.snapshot.overview.highRisk"
              class="risk-badge"
              :title="`待处置高风险事项：${store.snapshot.overview.highRisk} 项（未解决总量 ${(store.snapshot.overview.unresolvedIssues || 0).toLocaleString()} 项）`"
            >
              {{ store.snapshot.overview.highRisk }}
            </i>
          </RouterLink>
        </nav>

        <div class="status-divider"></div>

        <div class="header-status">
          <div class="status-item link-state" :class="{ error: store.connectionError, sync: store.loading }">
            <span class="link-dot"></span>
            <span>{{ store.connectionError ? '快照' : store.loading ? '同步' : '在线' }}</span>
          </div>
          <div class="status-item sync-time">
            <Activity :size="14" />
            <span class="clock-mono">{{ formattedClock }}</span>
          </div>
          <button class="header-btn" :class="{ spin: store.loading }" title="刷新数据" @click="handleManualRefresh">
            <RefreshCw :size="16" />
          </button>
          <button class="header-btn" :title="isFullscreen ? '退出全屏' : '全屏展示'" @click="toggleFullscreen">
            <Minimize v-if="isFullscreen" :size="16" />
            <Fullscreen v-else :size="16" />
          </button>
        </div>
      </div>
    </header>

    <!-- 连接警告 -->
    <div v-if="store.connectionError" class="connection-alert">
      <WifiOff :size="15" />
      <span>{{ store.connectionError }}</span>
      <button @click="handleManualRefresh">重试</button>
    </div>

    <!-- 主内容区：统一缩放视口，RouterView 内容落在固定画布上等比缩放 -->
    <main ref="viewportRef" class="command-main">
      <div
        class="screen-scale-box"
        :style="{
          width: `${baseWidth}px`,
          height: `${baseHeight}px`,
          transform: `scale(${scale})`,
        }"
      >
        <RouterView />
      </div>
    </main>

  </div>
</template>
