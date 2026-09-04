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
 * 关键修正：缩放系数必须用「缩放容器自身的内容尺寸」测量，
 * 而不是带 padding 的父级——否则系数偏大、画布比可视区宽，
 * 配合居中会导致左右两侧对称裁切（越窄裁得越狠），这正是此前 A 屏的病根。
 */
export function useScaleScreen(options: ScaleScreenOptions = {}) {
  const { baseWidth = 1920, baseHeight = 980, minScale = 0.55, maxScale = 1.35 } = options
  const scale = ref(1)
  const viewportRef = ref<HTMLElement | null>(null)

  function updateScale() {
    const el = viewportRef.value
    if (!el) return
    // clientWidth/Height 取的是内容盒（不含滚动条、不含自身 padding），
    // 即缩放画布真正可落位的区域，正是应当拿来算比例的尺寸。
    const w = el.clientWidth
    const h = el.clientHeight
    if (w <= 0 || h <= 0) return
    const fit = Math.min(w / baseWidth, h / baseHeight)
    scale.value = Math.max(minScale, Math.min(maxScale, fit))
  }

  let resizeObserver: ResizeObserver | null = null

  onMounted(() => {
    updateScale()
    window.addEventListener('resize', updateScale)
    if (viewportRef.value) {
      resizeObserver = new ResizeObserver(() => updateScale())
      resizeObserver.observe(viewportRef.value)
    }
  })

  onUnmounted(() => {
    window.removeEventListener('resize', updateScale)
    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }
  })

  return { scale, viewportRef, baseWidth, baseHeight, updateScale }
}
