import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import CockpitPanel from '../CockpitPanel.vue'

describe('CockpitPanel', () => {
  it('keeps the zone, title, and subtitle in one compact header row', () => {
    const wrapper = mount(CockpitPanel, {
      props: { zone: 'A1', title: '全域建设运行总览', subtitle: '建设、推广与风险同屏' },
      slots: { default: '<div>content</div>' },
    })

    const header = wrapper.get('header')
    const title = header.get('h3')
    const subtitle = header.get('span.text-slate-500')

    expect(header.classes()).toContain('items-center')
    expect(title.element.parentElement).toBe(subtitle.element.parentElement)
    expect(subtitle.classes()).toContain('truncate')
    expect(subtitle.classes()).not.toContain('block')
  })
})
