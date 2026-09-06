import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { nextTick } from 'vue'
import App from '../App.vue'

describe('App fullscreen navigation', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      statusText: 'offline test',
    }))
    Object.defineProperty(document, 'fullscreenElement', {
      value: null,
      configurable: true,
      writable: true,
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('keeps the command header visible after entering fullscreen', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', component: { template: '<div>screen</div>' } }],
    })
    await router.push('/')
    await router.isReady()

    const requestFullscreen = vi.fn(async () => {
      Object.defineProperty(document, 'fullscreenElement', {
        value: document.documentElement,
        configurable: true,
        writable: true,
      })
      document.dispatchEvent(new Event('fullscreenchange'))
    })
    Object.defineProperty(document.documentElement, 'requestFullscreen', {
      value: requestFullscreen,
      configurable: true,
    })

    const wrapper = mount(App, {
      global: { plugins: [createPinia(), router] },
    })

    const header = wrapper.get('.command-header')
    await wrapper.get('button[title="全屏展示"]').trigger('click')
    await nextTick()

    expect(requestFullscreen).toHaveBeenCalledOnce()
    expect(header.isVisible()).toBe(true)
    expect(wrapper.find('button[title="退出全屏"]').exists()).toBe(true)

    wrapper.unmount()
  })
})
