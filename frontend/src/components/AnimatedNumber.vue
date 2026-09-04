<script setup lang="ts">
/**
 * AnimatedNumber - GPU 加速的数字动画组件
 * 
 * 特点：
 * 1. 使用 requestAnimationFrame 实现平滑动画
 * 2. 缓动函数让过渡更自然
 * 3. CSS transform 触发 GPU 合成层
 * 4. 支持千分位格式化
 */
import { ref, watch, onMounted, onUnmounted } from 'vue'

const props = withDefaults(defineProps<{
  value: number
  duration?: number      // 动画时长 ms
  decimals?: number      // 小数位数
  separator?: string     // 千分位分隔符
  prefix?: string        // 前缀
  suffix?: string        // 后缀
  easing?: 'linear' | 'easeOut' | 'easeInOut'
}>(), {
  duration: 800,
  decimals: 0,
  separator: ',',
  prefix: '',
  suffix: '',
  easing: 'easeOut',
})

const displayValue = ref(0)
let animationId: number | null = null
let startTime: number | null = null
let startValue = 0

// 缓动函数
const easingFunctions = {
  linear: (t: number) => t,
  easeOut: (t: number) => 1 - Math.pow(1 - t, 3),
  easeInOut: (t: number) => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2,
}

// 格式化数字
const formatNumber = (num: number): string => {
  const fixed = num.toFixed(props.decimals)
  const [integer, decimal] = fixed.split('.')
  const formatted = integer.replace(/\B(?=(\d{3})+(?!\d))/g, props.separator)
  return decimal ? `${formatted}.${decimal}` : formatted
}

// 动画帧
const animate = (timestamp: number) => {
  if (!startTime) startTime = timestamp
  const elapsed = timestamp - startTime
  const progress = Math.min(elapsed / props.duration, 1)
  const easedProgress = easingFunctions[props.easing](progress)
  
  displayValue.value = startValue + (props.value - startValue) * easedProgress
  
  if (progress < 1) {
    animationId = requestAnimationFrame(animate)
  }
}

// 启动动画
const startAnimation = () => {
  if (animationId) {
    cancelAnimationFrame(animationId)
  }
  startValue = displayValue.value
  startTime = null
  animationId = requestAnimationFrame(animate)
}

// 监听值变化
watch(() => props.value, (newVal, oldVal) => {
  if (newVal !== oldVal) {
    startAnimation()
  }
})

onMounted(() => {
  displayValue.value = props.value
})

onUnmounted(() => {
  if (animationId) {
    cancelAnimationFrame(animationId)
  }
})
</script>

<template>
  <span class="animated-number">
    <span class="animated-number__prefix" v-if="prefix">{{ prefix }}</span>
    <span class="animated-number__value">{{ formatNumber(displayValue) }}</span>
    <span class="animated-number__suffix" v-if="suffix">{{ suffix }}</span>
  </span>
</template>

<style scoped>
.animated-number {
  display: inline-flex;
  align-items: baseline;
  /* GPU 加速：使用 transform 和 will-change */
  will-change: contents;
  transform: translateZ(0);
}

.animated-number__value {
  font-variant-numeric: tabular-nums;
  /* 等宽数字，防止宽度跳动 */
}

.animated-number__prefix,
.animated-number__suffix {
  opacity: 0.8;
}
</style>
