import { describe, expect, it } from 'vitest'
import {
  buildCoverageComposition,
  buildRolloutComposition,
  buildTaskStageSeries,
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
})
