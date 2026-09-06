import { ref, onMounted, onUnmounted } from 'vue'

export interface ScaleScreenOptions {
  baseWidth?: number
  baseHeight?: number
  /** 缩放下限：低于此值不再缩小，避免常规分辨率以下文字糊成一团。 */
  minScale?: number
  /** 缩放上限：高于此值不再放大，避免超大屏元素过疏、线条发虚。 */
  maxScale?: number
}

/**
 * useScaleScreen：大屏等比缩放引擎（全站统一骨架）
 *
 * 以 baseWidth×baseHeight 为唯一设计基准，用 GPU transform: scale 等比映射到任意视口。
 * 「屏」的分辨率差异全部由这里的等比缩放兜住；窗体内部的疏密由设计契约在基准尺寸上定死。
 *
 * 全屏模式：App.vue 隐藏 header，command-main 占满整屏。
 * 此时直接用 window.screen.width/height 计算，不再减 header 高度。
 */
export function useScaleScreen(options: ScaleScreenOptions = {}) {
  const { baseWidth = 1920, baseHeight = 980, minScale = 0.55, maxScale = 1.35 } = options
  const scale = ref(1)
  const viewportRef = ref<HTMLElement | null>(null)

  function updateScale() {
    const el = viewportRef.value
    if (!el) return

    let w: number
    let h: number

    if (document.fullscreenElement) {
      // 全屏模式：header 已隐藏，content-main 占满物理屏幕。
      // 直接用物理屏幕尺寸，不减 header。
      w = window.screen.width
      h = window.screen.height
    } else {
      // 普通模式：command-main 内容盒（不含滚动条与 padding）。
      w = el.clientWidth
      h = el.clientHeight
    }

    if (w <= 0 || h <= 0) return
    const fit = Math.min(w / baseWidth, h / baseHeight)
    scale.value = Math.max(minScale, Math.min(maxScale, fit))
  }

  const handleFullscreenChange = () => {
    // fullscreenchange 触发时布局可能尚未稳定，等下一帧再算。
    requestAnimationFrame(updateScale)
  }

  let resizeObserver: ResizeObserver | null = null

  onMounted(() => {
    updateScale()
    window.addEventListener('resize', updateScale)
    document.addEventListener('fullscreenchange', handleFullscreenChange)
    if (viewportRef.value) {
      resizeObserver = new ResizeObserver(updateScale)
      resizeObserver.observe(viewportRef.value)
    }
  })

  onUnmounted(() => {
    window.removeEventListener('resize', updateScale)
    document.removeEventListener('fullscreenchange', handleFullscreenChange)
    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }
  })

  return { scale, viewportRef, baseWidth, baseHeight, updateScale }
}
