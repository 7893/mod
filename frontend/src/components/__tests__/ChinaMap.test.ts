import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ChinaMap from '../ChinaMap.vue'

const ChartCanvasStub = defineComponent({
  props: {
    error: { type: String, default: null },
    loading: Boolean,
  },
  emits: ['chartClick'],
  template: `
    <div>
      <p v-if="error" data-test="map-error">{{ error }}</p>
      <p v-else-if="loading" data-test="map-loading">loading</p>
      <template v-else>
        <button data-test="single" @click="$emit('chartClick', { name: '广东', event: { event: {} } })">single</button>
        <button data-test="multiple" @click="$emit('chartClick', { name: '江苏', event: { event: { ctrlKey: true } } })">multiple</button>
      </template>
    </div>
  `,
})

describe('ChinaMap', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
  })

  it('reports that the deployment-owned map source is not configured', () => {
    vi.stubEnv('VITE_CHINA_MAP_GEOJSON_URL', '')
    const wrapper = mount(ChinaMap, {
      props: { data: [], selected: [] },
      global: { stubs: { ChartCanvas: ChartCanvasStub } },
    })

    expect(wrapper.get('[data-test="map-error"]').text()).toContain('VITE_CHINA_MAP_GEOJSON_URL')
  })

  it('emits ordinary and Ctrl clicks with their selection mode', async () => {
    vi.stubEnv('VITE_CHINA_MAP_GEOJSON_URL', '/deployment-owned/china.geojson')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        type: 'FeatureCollection',
        features: [{
          type: 'Feature',
          properties: { name: '广东' },
          geometry: { type: 'Polygon', coordinates: [] },
        }],
      }),
    }))
    const wrapper = mount(ChinaMap, {
      props: {
        data: [
          { name: '广东', value: 40, total: 10, launched: 6, dual: 2 },
          { name: '江苏', value: 60, total: 8, launched: 5, dual: 1 },
        ],
        selected: [],
      },
      global: {
        stubs: { ChartCanvas: ChartCanvasStub },
      },
    })
    await flushPromises()

    await wrapper.get('[data-test="single"]').trigger('click')
    await wrapper.get('[data-test="multiple"]').trigger('click')

    expect(wrapper.emitted('select')).toEqual([
      ['广东', false],
      ['江苏', true],
    ])
  })
})
