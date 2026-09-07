import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import AnimatedNumber from '../AnimatedNumber.vue'

describe('AnimatedNumber', () => {
  it('updates immediately when animation is disabled', async () => {
    const wrapper = mount(AnimatedNumber, {
      props: { value: 1, duration: 0, decimals: 1 },
    })

    await wrapper.setProps({ value: 42.5 })

    expect(wrapper.text()).toBe('42.5')
    expect(wrapper.text()).not.toContain('NaN')
  })
})
