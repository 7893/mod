import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { useScaleScreen, type ScaleScreenOptions } from '../useScaleScreen'

function runInSetup<T>(fn: () => T): { result: T; unmount: () => void } {
  let result!: T
  const comp = defineComponent({
    setup() {
      result = fn()
      return () => h('div')
    },
  })
  const wrapper = mount(comp)
  return { result, unmount: () => wrapper.unmount() }
}

describe('useScaleScreen', () => {
  let originalInnerWidth: number
  let originalInnerHeight: number

  beforeEach(() => {
    originalInnerWidth = window.innerWidth
    originalInnerHeight = window.innerHeight
  })

  afterEach(() => {
    Object.defineProperty(window, 'innerWidth', { value: originalInnerWidth, writable: true })
    Object.defineProperty(window, 'innerHeight', { value: originalInnerHeight, writable: true })
    vi.restoreAllMocks()
  })

  it('initializes with default options and scale 1', () => {
    const { result, unmount } = runInSetup(() => useScaleScreen())
    expect(result.scale.value).toBe(1)
    expect(result.baseWidth).toBe(1920)
    expect(result.baseHeight).toBe(980)
    expect(result.viewportRef.value).toBeNull()
    unmount()
  })

  it('does not crash or change scale when viewport element is null', () => {
    const { result, unmount } = runInSetup(() => useScaleScreen())
    result.updateScale()
    expect(result.scale.value).toBe(1)
    unmount()
  })

  it('calculates exact 1:1 scale when viewport matches base dimensions', () => {
    const { result, unmount } = runInSetup(() => useScaleScreen())
    const mockEl = document.createElement('div')
    Object.defineProperty(mockEl, 'clientWidth', { value: 1920, configurable: true })
    Object.defineProperty(mockEl, 'clientHeight', { value: 980, configurable: true })
    result.viewportRef.value = mockEl

    result.updateScale()
    expect(result.scale.value).toBe(1)
    unmount()
  })

  it('clamps to maxScale when viewport is ultra-wide / 4K', () => {
    const { result, unmount } = runInSetup(() => useScaleScreen({ maxScale: 1.35 }))
    const mockEl = document.createElement('div')
    Object.defineProperty(mockEl, 'clientWidth', { value: 3840, configurable: true })
    Object.defineProperty(mockEl, 'clientHeight', { value: 2160, configurable: true })
    result.viewportRef.value = mockEl

    result.updateScale()
    expect(result.scale.value).toBe(1.35)
    unmount()
  })

  it('clamps to minScale when viewport is very small', () => {
    const { result, unmount } = runInSetup(() => useScaleScreen({ minScale: 0.55 }))
    const mockEl = document.createElement('div')
    Object.defineProperty(mockEl, 'clientWidth', { value: 800, configurable: true })
    Object.defineProperty(mockEl, 'clientHeight', { value: 400, configurable: true })
    result.viewportRef.value = mockEl

    result.updateScale()
    expect(result.scale.value).toBe(0.55)
    unmount()
  })

  it('keeps the whole canvas visible on a narrow viewport by default', () => {
    const { result, unmount } = runInSetup(() => useScaleScreen())
    const mockEl = document.createElement('div')
    Object.defineProperty(mockEl, 'clientWidth', { value: 800, configurable: true })
    Object.defineProperty(mockEl, 'clientHeight', { value: 980, configurable: true })
    result.viewportRef.value = mockEl

    result.updateScale()
    expect(result.scale.value).toBeCloseTo(800 / 1920, 3)
    unmount()
  })

  it('scales proportionally based on limiting dimension (width-constrained)', () => {
    const { result, unmount } = runInSetup(() =>
      useScaleScreen({
        baseWidth: 1920,
        baseHeight: 980,
        minScale: 0.1,
        maxScale: 2.0,
      })
    )
    const mockEl = document.createElement('div')
    // 960 / 1920 = 0.5, 980 / 980 = 1.0 => min is 0.5
    Object.defineProperty(mockEl, 'clientWidth', { value: 960, configurable: true })
    Object.defineProperty(mockEl, 'clientHeight', { value: 980, configurable: true })
    result.viewportRef.value = mockEl

    result.updateScale()
    expect(result.scale.value).toBeCloseTo(0.5, 3)
    unmount()
  })

  it('scales proportionally based on limiting dimension (height-constrained)', () => {
    const { result, unmount } = runInSetup(() =>
      useScaleScreen({
        baseWidth: 1920,
        baseHeight: 980,
        minScale: 0.1,
        maxScale: 2.0,
      })
    )
    const mockEl = document.createElement('div')
    // 1920 / 1920 = 1.0, 490 / 980 = 0.5 => min is 0.5
    Object.defineProperty(mockEl, 'clientWidth', { value: 1920, configurable: true })
    Object.defineProperty(mockEl, 'clientHeight', { value: 490, configurable: true })
    result.viewportRef.value = mockEl

    result.updateScale()
    expect(result.scale.value).toBeCloseTo(0.5, 3)
    unmount()
  })

  it('preserves existing scale if dimensions are zero or negative', () => {
    const { result, unmount } = runInSetup(() => useScaleScreen())
    const mockEl = document.createElement('div')
    Object.defineProperty(mockEl, 'clientWidth', { value: 1920, configurable: true })
    Object.defineProperty(mockEl, 'clientHeight', { value: 980, configurable: true })
    result.viewportRef.value = mockEl
    result.updateScale()
    expect(result.scale.value).toBe(1)

    // Set clientWidth to 0
    Object.defineProperty(mockEl, 'clientWidth', { value: 0, configurable: true })
    result.updateScale()
    expect(result.scale.value).toBe(1)
    unmount()
  })

  it('keeps using the content viewport when document is in fullscreen mode', () => {
    const { result, unmount } = runInSetup(() =>
      useScaleScreen({
        baseWidth: 1920,
        baseHeight: 980,
        minScale: 0.2,
        maxScale: 2.0,
      })
    )
    const mockEl = document.createElement('div')
    Object.defineProperty(mockEl, 'clientWidth', { value: 1920, configurable: true })
    Object.defineProperty(mockEl, 'clientHeight', { value: 980, configurable: true })
    result.viewportRef.value = mockEl

    // Mock fullscreen
    const fsEl = document.createElement('div')
    Object.defineProperty(document, 'fullscreenElement', {
      value: fsEl,
      configurable: true,
      writable: true,
    })
    Object.defineProperty(window.screen, 'width', { value: 3840, configurable: true })
    Object.defineProperty(window.screen, 'height', { value: 2160, configurable: true })

    result.updateScale()
    expect(result.scale.value).toBe(1)

    // Clean up fullscreen mock
    Object.defineProperty(document, 'fullscreenElement', {
      value: null,
      configurable: true,
      writable: true,
    })
    unmount()
  })

  it('registers window resize and fullscreenchange listeners on mount, and cleans up on unmount', async () => {
    const addEventListenerSpy = vi.spyOn(window, 'addEventListener')
    const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener')
    const docAddSpy = vi.spyOn(document, 'addEventListener')
    const docRemoveSpy = vi.spyOn(document, 'removeEventListener')

    const TestComponent = defineComponent({
      setup() {
        const { scale, viewportRef } = useScaleScreen()
        return { scale, viewportRef }
      },
      render() {
        return h('div', { ref: 'viewportRef' }, 'test')
      },
    })

    const wrapper = mount(TestComponent)
    await nextTick()

    expect(addEventListenerSpy).toHaveBeenCalledWith('resize', expect.any(Function))
    expect(docAddSpy).toHaveBeenCalledWith('fullscreenchange', expect.any(Function))

    wrapper.unmount()

    expect(removeEventListenerSpy).toHaveBeenCalledWith('resize', expect.any(Function))
    expect(docRemoveSpy).toHaveBeenCalledWith('fullscreenchange', expect.any(Function))
  })
})
