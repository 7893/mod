import { describe, expect, it } from 'vitest'
import { parseEvent } from '../useLiveProjection'

describe('useLiveProjection committed event contract', () => {
  it('preserves the committed business narrative fields end to end', () => {
    const event = parseEvent(JSON.stringify({
      id: 'document-42',
      sequence: 7,
      occurred_at: '2026-09-09T12:00:00+08:00',
      business_type: 'integration_completed',
      increments: { documents: 1, vouchers: 1, integrations: 1 },
      cumulative: { documents: 7, vouchers: 7, integrations: 7 },
      projection_id: 'committed-simulator',
      unit_name: '测试单位',
      province: '北京',
      story_title: '费用报销单完成业务入账',
      story_desc: 'DOC-42 → V-42 · 集成成功',
      amount: '1688.00',
      badge_tone: 'success',
      batch_name: '第七批',
      mode: 'committed_simulation',
    }))

    expect(event.storyTitle).toBe('费用报销单完成业务入账')
    expect(event.storyDesc).toContain('集成成功')
    expect(event.amount).toBe('1688.00')
    expect(event.batchName).toBe('第七批')
  })
})

it('preserves explicit reset reasons from a persistent cursor state', () => {
  const event = parseEvent(JSON.stringify({
    id: 'outbox:stream-a:12', sequence: 12, business_type: 'projection_state',
    projection_id: 'stream-a', reset_required: true, reset_reason: 'cursor_unavailable',
  }))
  expect(event.resetRequired).toBe(true)
  expect(event.resetReason).toBe('cursor_unavailable')
})

import { vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { useLiveProjection } from '../useLiveProjection'

it('marks a source outage disconnected and does not show rejected duplicate events', () => {
  class FakeSource {
    static latest: FakeSource
    onopen?: () => void
    onerror?: () => void
    onmessage?: (event: { data: string }) => void
    listeners = new Map<string, () => void>()
    close = vi.fn()
    constructor() { FakeSource.latest = this }
    addEventListener(name: string, callback: () => void) { this.listeners.set(name, callback) }
  }
  vi.stubGlobal('EventSource', FakeSource)
  const handler = vi.fn().mockReturnValue(true)
  let projection!: ReturnType<typeof useLiveProjection>
  const wrapper = mount(defineComponent({ setup() {
    projection = useLiveProjection(handler)
    return () => h('div')
  } }))
  try {
    const source = FakeSource.latest
    source.onopen?.()
    expect(projection.connected.value).toBe(true)
    source.listeners.get('source_unavailable')?.()
    expect(projection.connected.value).toBe(false)
    const payload = { id: 'outbox:s:1', sequence: 1, business_type: 'integration_completed',
      projection_id: 's', story_title: '已提交事件' }
    source.onmessage?.({ data: JSON.stringify(payload) })
    expect(projection.connected.value).toBe(true)
    expect(projection.recentEvent.value?.storyTitle).toBe('已提交事件')
    handler.mockReturnValue(false)
    source.onmessage?.({ data: JSON.stringify({ ...payload, story_title: '重复事件' }) })
    expect(projection.recentEvent.value?.storyTitle).toBe('已提交事件')
    source.onmessage?.({ data: JSON.stringify({ ...payload, reset_required: true,
      business_type: 'projection_state' }) })
    expect(projection.recentEvent.value).toBeNull()
  } finally {
    wrapper.unmount()
    expect(FakeSource.latest.close).toHaveBeenCalled()
    vi.unstubAllGlobals()
  }
})
