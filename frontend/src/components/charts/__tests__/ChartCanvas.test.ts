import { mount } from '@vue/test-utils'
import type { EChartsOption } from 'echarts'
import { describe, expect, it, vi } from 'vitest'

vi.mock('vue-echarts', () => ({
  default: {
    name: 'VChart',
    props: ['option'],
    emits: ['click'],
    template: '<button class="v-chart-mock" @click="$emit(\'click\', { name: \'已导入\' })" />',
  },
}))

import VChart from 'vue-echarts'
import ChartCanvas from '../ChartCanvas.vue'

describe('ChartCanvas', () => {
  it('renders an option and forwards semantic chart clicks', async () => {
    const option = { series: [{ type: 'pie', data: [1] }] } satisfies EChartsOption
    const wrapper = mount(ChartCanvas, { props: { option } })

    expect(wrapper.findComponent(VChart).props('option')).toEqual(option)
    await wrapper.find('.v-chart-mock').trigger('click')
    expect(wrapper.emitted('chartClick')).toEqual([[{ name: '已导入' }]])
  })

  it('renders shared non-chart states', () => {
    const states = [
      mount(ChartCanvas, { props: { loading: true } }),
      mount(ChartCanvas, { props: { error: '图表加载失败' } }),
      mount(ChartCanvas, { props: { empty: true, emptyText: '暂无门禁数据' } }),
    ]

    expect(states[0].text()).toContain('数据加载中')
    expect(states[1].text()).toContain('图表加载失败')
    expect(states[2].text()).toContain('暂无门禁数据')
    expect(states.every((wrapper) => !wrapper.findComponent(VChart).exists())).toBe(true)
  })
})
