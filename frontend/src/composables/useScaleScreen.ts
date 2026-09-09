import { ref, onMounted, onUnmounted } from 'vue'

export interface ScaleScreenOptions {
  baseWidth?: number
  baseHeight?: number
  /** 缩放下限：默认允许完整画布继续缩小；调用方仅在明确接受裁切时覆盖。 */
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
 * 普通与全屏模式都保留导航栏，因此始终以 command-main 的真实内容盒计算。
 * fullscreenchange 只负责在浏览器完成布局切换后重新测量。
 */
export function useScaleScreen(options: ScaleScreenOptions = {}) {
  const { baseWidth = 1920, baseHeight = 980, minScale = 0.1, maxScale = 1.35 } = options
  const scale = ref(1)
  const viewportRef = ref<HTMLElement | null>(null)

  function updateScale() {
    const el = viewportRef.value
    if (!el) return

    // command-main 内容盒已经扣除了常驻导航栏高度；使用真实布局尺寸
    // 可避免全屏时按物理屏幕高度放大画布、造成导航与内容重叠。
    const w = el.clientWidth
    const h = el.clientHeight

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
