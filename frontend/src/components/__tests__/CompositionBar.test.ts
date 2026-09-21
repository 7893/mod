import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

vi.mock('../charts/ChartCanvas.vue', () => ({
  default: {
    name: 'ChartCanvas',
    props: ['option'],
    template: '<div class="chart-canvas-mock" />',
  },
}))

import ChartCanvas from '../charts/ChartCanvas.vue'
import CompositionBar from '../blocks/CompositionBar.vue'

describe('CompositionBar', () => {
  it('renders its chart through the shared canvas and keeps exact values visible', () => {
    const wrapper = mount(CompositionBar, {
      props: {
        total: 10,
        parts: [
          { label: '已完成', value: 7, percentage: 70, tone: 'success' },
          { label: '待处理', value: 3, percentage: 30, tone: 'warning' },
        ],
      },
    })

    expect(wrapper.findComponent(ChartCanvas).exists()).toBe(true)
    expect(wrapper.findComponent(ChartCanvas).props('option')).toBeTruthy()
    expect(wrapper.text()).toContain('已完成')
    expect(wrapper.text()).toContain('7')
    expect(wrapper.text()).toContain('待处理')
    expect(wrapper.text()).toContain('3')
  })
})
