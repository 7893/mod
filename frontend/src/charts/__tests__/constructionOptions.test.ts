import { describe, expect, it } from 'vitest'
import {
  createTrainingConversionOption,
  createTrainingMixOption,
} from '../constructionOptions.ts'

const trainingTypes = [
  { type: '业务操作培训', count: 12, expected: 120, actual: 110, passed: 105, cert: 80 },
  { type: '项目管理培训', count: 8, expected: 90, actual: 85, passed: 82, cert: 60 },
]

describe('construction training charts', () => {
  it('keeps all four conversion stages for every training type', () => {
    const option = createTrainingConversionOption(trainingTypes)

    expect(option.series).toHaveLength(4)
    expect(option.series.map((series) => series.name)).toEqual(['应到', '实到', '通过', '认证'])
    expect(option.series[0].data).toEqual([120, 90])
    expect(option.series[3].data).toEqual([80, 60])
  })

  it('derives the session mix without inventing totals', () => {
    const option = createTrainingMixOption(trainingTypes)

    expect(option.series[0].data.map((item) => item.value)).toEqual([12, 8])
  })
})
