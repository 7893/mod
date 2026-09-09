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
