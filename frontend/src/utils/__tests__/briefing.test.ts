import { describe, expect, it } from 'vitest'
import { parseBriefingSections } from '../briefing.ts'

describe('parseBriefingSections', () => {
  it('turns the daily markdown briefing into scan-friendly sections', () => {
    const result = parseBriefingSections(`
# 智能研判报告
**整体推进成效**
- 已完成前四批上线
- 凭证生成保持稳定

**关键瓶颈聚焦：**
1. 第六批仍有核对差异

## 管理行动建议
* 优先督导重点单位
`)

    expect(result).toEqual([
      { title: '整体推进成效', items: ['已完成前四批上线', '凭证生成保持稳定'] },
      { title: '关键瓶颈聚焦', items: ['第六批仍有核对差异'] },
      { title: '管理行动建议', items: ['优先督导重点单位'] },
    ])
  })

  it('keeps plain text in a fallback summary card', () => {
    expect(parseBriefingSections('今日运行稳定。\n重点关注第六批。')).toEqual([
      { title: '简报摘要', items: ['今日运行稳定。', '重点关注第六批。'] },
    ])
  })

  it('returns no cards for an empty briefing', () => {
    expect(parseBriefingSections(null)).toEqual([])
  })
})
