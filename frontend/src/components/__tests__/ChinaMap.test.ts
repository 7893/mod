import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ChinaMap from '../ChinaMap.vue'

const ChartCanvasStub = defineComponent({
  emits: ['chartClick'],
  template: `
    <div>
      <button data-test="single" @click="$emit('chartClick', { name: '广东', event: { event: {} } })">single</button>
      <button data-test="multiple" @click="$emit('chartClick', { name: '江苏', event: { event: { ctrlKey: true } } })">multiple</button>
    </div>
  `,
})

describe('ChinaMap', () => {
  it('emits ordinary and Ctrl clicks with their selection mode', async () => {
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

    await wrapper.get('[data-test="single"]').trigger('click')
    await wrapper.get('[data-test="multiple"]').trigger('click')

    expect(wrapper.emitted('select')).toEqual([
      ['广东', false],
      ['江苏', true],
    ])
  })
})
