import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('vue-echarts', () => ({
  default: {
    name: 'VChart',
    props: ['option'],
    template: '<div class="v-chart-mock" :data-option="JSON.stringify(option)" />',
  },
}))

import VChart from 'vue-echarts'
import OverviewTrendChart from '../OverviewTrendChart.vue'

describe('OverviewTrendChart', () => {
  it('renders 7 items directly and ensures tooltip confinement (KI-065)', () => {
    const data = [
      { date: '08-30', fullDate: '2026-08-30', launched: 748, dual: 205 },
      { date: '09-01', fullDate: '2026-09-01', launched: 1002, dual: 0 },
      { date: '09-07', fullDate: '2026-09-07', launched: 1002, dual: 0 },
      { date: '09-09', fullDate: '2026-09-09', launched: 1192, dual: 333 },
      { date: '09-14', fullDate: '2026-09-14', launched: 1002, dual: 0 },
      { date: '09-21', fullDate: '2026-09-21', launched: 1002, dual: 0 },
      { date: '09-28', fullDate: '2026-09-28', launched: 1002, dual: 0 },
    ]

    const wrapper = mount(OverviewTrendChart, {
      props: { data },
    })

    const stub = wrapper.findComponent(VChart)
    expect(stub.exists()).toBe(true)
    const option = stub.props('option') as any
    expect(option.tooltip.confine).toBe(true)
    expect(option.xAxis.data).toEqual([
      '08-30', '09-01', '09-07', '09-09', '09-14', '09-21', '09-28',
    ])
    // 09-09 is at index 3 (center of 7 items)
    expect(option.xAxis.data[3]).toBe('09-09')
  })

  it('symmetrically windows long datasets around today (KI-065)', () => {
    const now = new Date()
    const mm = String(now.getMonth() + 1).padStart(2, '0')
    const dd = String(now.getDate()).padStart(2, '0')
    const today = `${mm}-${dd}`

    const data = [
      { date: '08-15', fullDate: '2026-08-15', launched: 700, dual: 100 },
      { date: '08-22', fullDate: '2026-08-22', launched: 720, dual: 150 },
      { date: '08-30', fullDate: '2026-08-30', launched: 748, dual: 205 },
      { date: '09-01', fullDate: '2026-09-01', launched: 1002, dual: 0 },
      { date: '09-07', fullDate: '2026-09-07', launched: 1002, dual: 0 },
      { date: today, fullDate: `2026-${today}`, launched: 1192, dual: 333 },
      { date: '09-14', fullDate: '2026-09-14', launched: 1002, dual: 0 },
      { date: '09-21', fullDate: '2026-09-21', launched: 1002, dual: 0 },
      { date: '09-28', fullDate: '2026-09-28', launched: 1002, dual: 0 },
      { date: '10-01', fullDate: '2026-10-01', launched: 1002, dual: 0 },
    ]

    const wrapper = mount(OverviewTrendChart, {
      props: { data },
    })

    const stub = wrapper.findComponent(VChart)
    expect(stub.exists()).toBe(true)
    const option = stub.props('option') as any
    expect(option.xAxis.data).toHaveLength(7)
    // Today is centered at index 3
    expect(option.xAxis.data[3]).toBe(today)
  })
})
