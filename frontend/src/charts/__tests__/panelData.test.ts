import { describe, expect, it } from 'vitest'
import {
  buildBatchOverviewSeries,
  buildBatchProgressSeries,
  buildCoverageComposition,
  buildOverviewComposition,
  buildRolloutComposition,
  buildTaskStageSeries,
  parsePercentage,
} from '../panelData'

describe('charts/panelData', () => {
  it('normalizes task stage values for stacked charts', () => {
    expect(buildTaskStageSeries([
      { name: '接口联调', total: 10, completed: 6, inProgress: 3, notStarted: 1, avgProgress: 72.345 },
    ])).toEqual([
      { name: '接口联调', completed: 6, inProgress: 3, notStarted: 1, progress: 72.345 },
    ])
  })

  it('derives pending rollout units without producing negative values', () => {
    expect(buildRolloutComposition([
      { name: '第一批', total: 100, launched: 70, dual: 20 },
      { name: '第二批', total: 10, launched: 12, dual: 1 },
    ])).toEqual([
      { name: '第一批', launched: 70, dual: 20, pending: 10 },
      { name: '第二批', launched: 12, dual: 1, pending: 0 },
    ])
  })

  it('returns honest coverage values and rejects missing totals', () => {
    expect(buildCoverageComposition(2000, 1950)).toEqual({ covered: 1950, gap: 50, rate: 97.5 })
    expect(buildCoverageComposition(100, 120)).toEqual({ covered: 100, gap: 0, rate: 100 })
    expect(buildCoverageComposition(null, null)).toBeNull()
    expect(buildCoverageComposition(0, 0)).toBeNull()
  })

  it('normalizes batch progress percentages for comparison charts', () => {
    expect(buildBatchProgressSeries([
      { name: '第一批', constructionPct: 108, launchedPct: 82.5 },
      { name: '第二批', constructionPct: Number.NaN, launchedPct: -4 },
    ])).toEqual([
      { name: '第一批', construction: 100, launched: 82.5 },
      { name: '第二批', construction: 0, launched: 0 },
    ])
  })

  it('parses numeric-string percentages without turning missing values into data', () => {
    expect(parsePercentage('65.4')).toBe(65.4)
    expect(parsePercentage(108)).toBe(100)
    expect(parsePercentage(null)).toBeNull()
    expect(parsePercentage('not-a-number')).toBeNull()
  })

  it('condenses completed batches while retaining active rollout rows', () => {
    expect(buildBatchOverviewSeries([
      { name: '第一批', constructionPct: 100, launchedPct: 100 },
      { name: '第二批', constructionPct: 100, launchedPct: 100 },
      { name: '第三批', constructionPct: 72.5, launchedPct: 0 },
    ])).toEqual([
      { name: '已完成2批', construction: 100, launched: 100 },
      { name: '第三批', construction: 72.5, launched: 0 },
    ])
  })

  it('builds honest overview composition percentages from numeric strings', () => {
    expect(buildOverviewComposition('100', [
      { label: '已完成', value: '58', tone: 'success' },
      { label: '进行中', value: 14, tone: 'accent' },
      { label: '未开始', value: -3, tone: 'neutral' },
    ])).toEqual({
      total: 100,
      parts: [
        { label: '已完成', value: 58, percentage: 58, tone: 'success' },
        { label: '进行中', value: 14, percentage: 14, tone: 'accent' },
        { label: '未开始', value: 0, percentage: 0, tone: 'neutral' },
      ],
    })
  })
})
