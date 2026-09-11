import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { expect, it } from 'vitest'
import DrawerShell from '../DrawerShell.vue'

it('contains keyboard focus, closes on Escape and restores the opener', async () => {
  const opener = document.createElement('button')
  document.body.append(opener)
  opener.focus()
  const wrapper = mount(DrawerShell, {
    attachTo: document.body,
    props: { label: '测试详情' },
    slots: { default: '<button>关闭</button><button>末尾</button>' },
  })
  await nextTick()
  const buttons = wrapper.findAll('button')
  expect(document.activeElement).toBe(buttons[0].element)
  await buttons[0].trigger('keydown', { key: 'Tab', shiftKey: true })
  expect(document.activeElement).toBe(buttons[1].element)
  await buttons[1].trigger('keydown', { key: 'Tab' })
  expect(document.activeElement).toBe(buttons[0].element)
  await buttons[0].trigger('keydown', { key: 'Escape' })
  expect(wrapper.emitted('close')).toHaveLength(1)
  wrapper.unmount()
  expect(document.activeElement).toBe(opener)
  opener.remove()
})
