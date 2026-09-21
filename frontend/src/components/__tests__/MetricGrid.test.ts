import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import AnimatedNumber from '../AnimatedNumber.vue'
import MetricGrid from '../blocks/MetricGrid.vue'

describe('MetricGrid', () => {
  it('uses the shared number animation for live numeric metrics', () => {
    const wrapper = mount(MetricGrid, {
      props: {
        items: [{ label: '今日业务单据', value: 1280, prefix: '+', animate: true }],
        align: 'center',
      },
    })

    const number = wrapper.getComponent(AnimatedNumber)
    expect(number.props('value')).toBe(1280)
    expect(number.props('prefix')).toBe('+')
    expect(wrapper.get('.metric-grid').classes()).toContain('metric-grid--center')
  })
})
