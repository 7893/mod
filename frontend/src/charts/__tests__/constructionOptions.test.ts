import { describe, expect, it } from 'vitest'
import {
  createReadinessPieOption,
  createTaskStageMatrixOption,
  createTrainingConversionOption,
  createTrainingMixOption,
} from '../constructionOptions.ts'

const taskStages = Array.from({ length: 8 }, (_, index) => ({
  name: `阶段${index + 1}`,
  completed: 60 + index,
  inProgress: 20,
  notStarted: 20 - index,
  progress: 60 + index,
}))

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

describe('construction command charts', () => {
  it('renders every stage and status as one matrix cell', () => {
    const option = createTaskStageMatrixOption(taskStages)

    expect(option.series[0].type).toBe('heatmap')
    expect(option.series[0].data).toHaveLength(24)
    expect(option.xAxis.data).toHaveLength(8)
    expect(option.yAxis.data).toEqual(['已完成', '进行中', '未开始'])
    expect(option.visualMap.show).toBe(false)
  })

  it('maps every readiness state without changing its drill-down label', () => {
    const option = createReadinessPieOption({
      imported: 12,
      verified: 9,
      collecting: 4,
      notCollected: 2,
    })

    expect(option.series[0].data.map((item) => item.name)).toEqual([
      '已导入', '已校验', '收集中', '未收集',
    ])
    expect(option.series[0].data.map((item) => item.value)).toEqual([12, 9, 4, 2])
    expect(option.tooltip.confine).toBe(true)
  })

  it('keeps missing readiness data honest as zero-valued segments', () => {
    const option = createReadinessPieOption()

    expect(option.series[0].data.map((item) => item.value)).toEqual([0, 0, 0, 0])
  })
})
