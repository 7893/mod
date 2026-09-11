import { test as base, expect } from '@playwright/test'
import snapshotData from '../src/data/fallback-snapshot.json' with { type: 'json' }

export const snapshot = structuredClone(snapshotData)
export const unit = snapshot.entities[0]!
export const issue = {
  id: 'ISS-VISUAL-001', unitId: unit.id, unitName: unit.name, province: unit.province,
  batchId: 1, issueType: '票据异常', severity: 'MEDIUM', status: 'RESOLVED', owner: '模拟专班',
  title: '冻结验收工单', description: '这是一条固定的治理事件，用于验证巡航与工单同源。',
  aiEnriched: 0, reworkCount: 0, createdAt: '2026-09-11 09:00:00',
  updatedAt: '2026-09-11 10:00:00', resolvedAt: '2026-09-11 10:00:00',
}
export const activity = {
  id: 1, issueId: issue.id, action: '闭环销项', actor: '模拟专班', detail: issue.description,
  timeStr: '10:00:00', occurredAt: issue.updatedAt, unitName: unit.name,
  province: unit.province, issueType: issue.issueType, status: issue.status,
}

export const test = base.extend({
  page: async ({ page }, use) => {
    const unexpected: string[] = []
    const errors: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    await page.clock.install({ time: new Date('2026-09-11T02:00:00Z') })
    await page.clock.pauseAt(new Date('2026-09-11T02:00:00Z'))
    await page.route('**/*', async route => {
      const url = new URL(route.request().url())
      if (url.origin !== 'http://127.0.0.1:4187') {
        unexpected.push(url.origin); await route.abort(); return
      }
      if (!url.pathname.startsWith('/api/')) { await route.continue(); return }
      if (route.request().method() !== 'GET') {
        unexpected.push(route.request().method() + ' ' + url.pathname); await route.abort(); return
      }
      let data: unknown
      if (url.pathname === '/api/dashboard/snapshot') data = { ...snapshot, meta: { ...snapshot.meta, source: 'live', asOfDate: '2026-09-11', generatedAt: '2026-09-11 10:00:00' } }
      else if (url.pathname === '/api/insights/briefing') data = { status: 'no_briefing' }
      else if (url.pathname === '/api/insights/status') data = { automlStatus: 'NOT_EVALUATED', hw_ml: { status: 'unavailable' }, cf_ai: { status: 'disabled' } }
      else if (url.pathname === '/api/governance/recent-activities') data = [activity]
      else if (url.pathname === '/api/governance/ai-quota') data = { status: 'ACTIVE', dailyLimit: 3000, neuronsUsed: 0, remainingNeurons: 3000, usagePct: 0 }
      else if (url.pathname === `/api/governance/issues/${issue.id}`) data = issue
      else if (url.pathname.endsWith('/timeline')) data = [activity]
      else if (url.pathname === '/api/governance/issues') data = { items: [issue] }
      else if (url.pathname.includes('/risk-explanation/')) data = { source: 'UNAVAILABLE', factors: [] }
      else if (url.pathname === '/api/live-projection/events') {
        await route.fulfill({ contentType: 'text/event-stream', body: ': offline fixture\n\n' }); return
      } else {
        unexpected.push(url.pathname); await route.fulfill({ status: 501, json: {} }); return
      }
      await route.fulfill({ json: data })
    })
    await use(page)
    expect(unexpected, 'All browser requests must be isolated fixtures').toEqual([])
    expect(errors, 'No browser runtime errors').toEqual([])
  },
})
export { expect }
