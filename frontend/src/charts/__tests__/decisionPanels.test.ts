import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { createLaunchGateOption } from '../constructionOptions'
import { createOperationsTrendOption, createQualityAuditVolumeOption } from '../operationsOptions'
import { createCoverageOption, createOperationalGuardOption } from '../panelOptions'
import { createRolloutTrendMatrixOption } from '../rolloutOptions'
import { chartTooltip } from '../theme'

describe('decision panel options', () => {
  it('keeps the five stable zones while replacing their low-value titles', () => {
    const sources = {
      dashboard: readFileSync(resolve(process.cwd(), 'src/views/DashboardView.vue'), 'utf8'),
      construction: readFileSync(resolve(process.cwd(), 'src/views/ConstructionView.vue'), 'utf8'),
      rollout: readFileSync(resolve(process.cwd(), 'src/views/RolloutView.vue'), 'utf8'),
      operations: readFileSync(resolve(process.cwd(), 'src/views/OperationsView.vue'), 'utf8'),
      theme: readFileSync(resolve(process.cwd(), 'src/styles/theme.css'), 'utf8'),
    }

    expect(sources.dashboard).toContain('title="运营红线哨位"')
    expect(sources.dashboard).toContain('zone="A8"')
    expect(sources.dashboard).not.toContain('title="项目联系人覆盖"')
    expect(sources.construction).toContain('title="上线门禁攻坚"')
    expect(sources.construction).toContain('zone="B4"')
    expect(sources.rollout).toContain('title="批次上线爬坡矩阵"')
    expect(sources.rollout).toContain('zone="C3"')
    expect(sources.operations).toContain('title="近 7 日业务吞吐"')
    expect(sources.operations).toContain('zone="D3"')
    expect(sources.operations).toContain('zone="D7"')
    expect(sources.operations).not.toContain('title="链路规模对比"')
    expect(sources.dashboard).toContain('grid-rows-dashboard-stack')
    expect(sources.dashboard).toContain(':disabled="!briefingSummary"')
    expect(sources.dashboard).not.toContain('v-if="briefingSummary"')
    expect(sources.construction).toContain('grid-rows-construction')
    expect(sources.rollout).toContain('grid-cols-rollout-analysis')
    expect(sources.rollout).toContain('class="col-span-8 row-span-2"')
    expect(sources.rollout).not.toContain('ChartBlock :stats="c4Stats"')
    expect(sources.theme).toContain('--grid-template-rows-construction: minmax(0, 1.1fr) minmax(0, 0.9fr)')
    expect(sources.theme).toContain('--grid-template-rows-rollout-body: minmax(0, 1.25fr) minmax(0, 0.75fr)')
  })

  it('builds the A8 guard chart without converting missing data into a visible count', () => {
    const option = createOperationalGuardOption([
      { name: '接口失败', value: 8, tone: 'danger' },
      { name: '双轨差异', value: null, tone: 'warning' },
      { name: '金标异常', value: 0, tone: 'accent' },
    ])

    expect(option.yAxis.data).toEqual(['金标异常', '双轨差异', '接口失败'])
    const formatter = option.series[0].label.formatter as (params: { dataIndex: number }) => string
    expect(formatter({ dataIndex: 1 })).toBe('—')
  })

  it('builds the B4 launch gates as a three-state composition', () => {
    const option = createLaunchGateOption([
      { name: '接口联调', completed: 60, inProgress: 30, notStarted: 10, progress: 72 },
    ])

    expect(option.series.map((series) => series.name)).toEqual(['已完成', '进行中', '待启动'])
    expect(option.series.map((series) => series.data[0])).toEqual([60, 30, 10])
  })

  it('builds the C3 batch-by-date heatmap with rollout context', () => {
    const option = createRolloutTrendMatrixOption([
      { date: '09-01', batchId: 1, name: '第一批', total: 100, launchedPct: 80, dualPct: 15 },
      { date: '09-08', batchId: 1, name: '第一批', total: 100, launchedPct: 90, dualPct: 8 },
      { date: '09-08', batchId: 2, name: '第二批', total: 120, launchedPct: 60, dualPct: 25 },
    ])

    expect(option.xAxis.data).toEqual(['09-01', '09-08'])
    expect(option.yAxis.data).toEqual(['第一批', '第二批'])
    expect(option.series[0].type).toBe('heatmap')
    expect(option.series[0].data).toHaveLength(3)
  })

  it('builds the D3 daily-volume bars and quality line', () => {
    const option = createOperationsTrendOption([
      { date: '09-08', documents: 20, vouchers: 18, integrations: 18, integrationSuccessPct: 94.4 },
    ])

    expect(option.series.map((series) => series.type)).toEqual(['bar', 'bar', 'line'])
    expect(option.series[2].data).toEqual([94.4])
    expect('legend' in option).toBe(false)
  })

  it('uses checked volume rather than four identical compliance bars in D7', () => {
    const option = createQualityAuditVolumeOption([
      { rule: '借贷平衡核验', total: 1_000_000, errors: 0, rate: 100, unit: '张凭证' },
      { rule: '状态演进追踪', total: 2_000, errors: 3, rate: 99.85, unit: '家单位' },
    ])

    const values = option.series[0].data.map((item) => item.value)
    expect(values[0]).not.toBe(values[1])
    expect(values.every((value) => value < 10)).toBe(true)
  })

  it('builds C5 coverage ring without center title and with confined tooltip (KI-065)', () => {
    const option = createCoverageOption({ rate: 85.5, covered: 1710, gap: 290 })
    expect(option).not.toHaveProperty('title')
    expect(option.tooltip.confine).toBe(true)
    const formatter = option.tooltip.formatter as (params: any) => string
    const tip = formatter({ name: '已覆盖单位', value: 1710, percent: 85.5 })
    expect(tip).toContain('85.5%')
    expect(tip).toContain('已覆盖单位')
    expect(tip).toContain('1,710')
  })

  it('enforces confine: true baseline on chartTooltip to prevent overflow (KI-065)', () => {
    expect(chartTooltip.confine).toBe(true)
  })
})
