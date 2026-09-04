<script setup lang="ts">
/**
 * AnimatedProgress - GPU 加速的进度条组件
 * 
 * 使用 CSS transform: scaleX() 实现动画
 * 比 width 动画性能更好（不触发重排）
 */
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  value: number          // 0-100
  color?: string         // 进度条颜色
  bgColor?: string       // 背景色
  height?: number        // 高度 px
  rounded?: boolean      // 圆角
  showLabel?: boolean    // 显示百分比
  duration?: number      // 动画时长 ms
}>(), {
  color: '#4a9eff',
  bgColor: 'rgba(74, 158, 255, 0.15)',
  height: 8,
  rounded: true,
  showLabel: false,
  duration: 600,
})

const clampedValue = computed(() => Math.max(0, Math.min(100, props.value)))

const barStyle = computed(() => ({
  '--progress': clampedValue.value / 100,
  '--color': props.color,
  '--bg-color': props.bgColor,
  '--height': `${props.height}px`,
  '--duration': `${props.duration}ms`,
  '--radius': props.rounded ? `${props.height / 2}px` : '0',
}))
</script>

<template>
  <div class="animated-progress" :style="barStyle">
    <div class="animated-progress__track">
      <div class="animated-progress__fill"></div>
    </div>
    <span v-if="showLabel" class="animated-progress__label">
      {{ clampedValue.toFixed(1) }}%
    </span>
  </div>
</template>

<style scoped>
.animated-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.animated-progress__track {
  flex: 1;
  height: var(--height);
  background: var(--bg-color);
  border-radius: var(--radius);
  overflow: hidden;
  /* GPU 加速 */
  transform: translateZ(0);
  will-change: transform;
}

.animated-progress__fill {
  height: 100%;
  background: var(--color);
  border-radius: var(--radius);
  /* 使用 scaleX 而不是 width，触发 GPU 合成 */
  transform: scaleX(var(--progress));
  transform-origin: left center;
  transition: transform var(--duration) cubic-bezier(0.4, 0, 0.2, 1);
  will-change: transform;
}

.animated-progress__label {
  min-width: 48px;
  font-size: 12px;
  font-weight: 500;
  color: var(--color);
  text-align: right;
  font-variant-numeric: tabular-nums;
}
</style>
