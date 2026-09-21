import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { createLaunchGateOption } from '../constructionOptions'
import { createOperationsTrendOption, createQualityAuditVolumeOption } from '../operationsOptions'
import { createCoverageOption } from '../panelOptions'
import { createRolloutTrendMatrixOption } from '../rolloutOptions'
import { chartTooltip } from '../theme'
import { CHART_FONT } from '../tokens'

describe('decision panel options', () => {
  it('keeps each decision fact in one visible panel', () => {
    const sources = {
      dashboard: readFileSync(resolve(process.cwd(), 'src/views/DashboardView.vue'), 'utf8'),
      topBar: readFileSync(resolve(process.cwd(), 'src/components/CockpitTopBar.vue'), 'utf8'),
      construction: readFileSync(resolve(process.cwd(), 'src/views/ConstructionView.vue'), 'utf8'),
      rollout: readFileSync(resolve(process.cwd(), 'src/views/RolloutView.vue'), 'utf8'),
      operations: readFileSync(resolve(process.cwd(), 'src/views/OperationsView.vue'), 'utf8'),
      issues: readFileSync(resolve(process.cwd(), 'src/views/IssuesView.vue'), 'utf8'),
      insights: readFileSync(resolve(process.cwd(), 'src/views/InsightsView.vue'), 'utf8'),
      theme: readFileSync(resolve(process.cwd(), 'src/styles/theme.css'), 'utf8'),
    }

    expect(sources.dashboard).toContain('title="跨域行动"')
    expect(sources.dashboard).not.toContain('zone="A3"')
    expect(sources.dashboard).not.toContain('zone="A8"')
    expect(sources.topBar).toContain('title="五域指挥入口"')
    expect(sources.topBar).not.toContain('ChartCanvas')
    expect(sources.topBar).toContain("detail: '单据凭证全链路'")
    expect(sources.topBar).not.toContain('今日单据')
    expect(sources.dashboard).toContain("label: '纳入单位'")
    expect(sources.dashboard).toContain("label: '上线率'")
    expect(sources.dashboard).toContain("label: '尚未上线'")
    expect(sources.dashboard).not.toContain("label: '今日单据'")
    expect(sources.dashboard).toContain('<MetricGrid :items="provinceFacts" :columns="3"')
    expect(sources.construction).toContain('title="上线门禁攻坚"')
    expect(sources.construction).toContain('zone="B4"')
    expect(sources.construction).toContain('title="建设台账预览"')
    expect(sources.construction).toContain('zone="B6"')
    expect(sources.construction).not.toContain('activeTab')
    expect(sources.construction).not.toContain('createTaskStageRadarOption')
    expect(sources.rollout).toContain('title="批次推进全景"')
    expect(sources.rollout).toContain('zone="C2"')
    expect(sources.rollout).not.toContain('zone="C3"')
    expect(sources.rollout).toContain('title="省域推进缺口"')
    expect(sources.operations).toContain('title="近 7 日业务吞吐"')
    expect(sources.operations).toContain('zone="D3"')
    expect(sources.operations).toContain('zone="D7"')
    expect(sources.operations).toContain('class="col-span-5 pr-3 border-r border-surface-veil-06"')
    expect(sources.operations).toContain("item.rate != null ? `${item.rate}%` : '未核验'")
    expect(sources.operations).toContain('title="端到端业务链路"')
    expect(sources.operations).not.toContain('zone="D2"')
    expect(sources.issues).toContain('title="近期工单流转"')
    expect(sources.issues).not.toContain('title="合规评级构成"')
    expect(sources.insights).toContain('title="风险决策摘要"')
    expect(sources.insights).not.toContain('createRiskOverviewOption')
    expect(sources.dashboard).toContain(':disabled="!briefingSummary"')
    expect(sources.dashboard).not.toContain('v-if="briefingSummary"')
    expect(sources.construction).toContain('grid-rows-construction')
    expect(sources.rollout).toContain('grid-cols-rollout-analysis')
    expect(sources.rollout).toContain('class="col-span-8 row-span-2"')
    expect(sources.rollout).not.toContain('ChartBlock :stats="c4Stats"')
    expect(sources.theme).toContain('--grid-template-rows-construction: minmax(0, 1fr) minmax(0, 0.85fr) minmax(0, 0.55fr)')
    expect(sources.theme).toContain('--grid-template-rows-dashboard-left: minmax(0, 1.1fr) minmax(0, 0.9fr)')
    expect(sources.theme).toContain('--grid-template-rows-rollout-body: minmax(0, 1.1fr) minmax(0, 0.9fr)')
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
    expect(option.series[0].label.fontSize).toBe(CHART_FONT.body)
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
    expect(option.series[0].label.fontSize).toBe(CHART_FONT.body)
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
