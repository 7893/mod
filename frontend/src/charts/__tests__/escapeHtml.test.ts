import { describe, expect, it } from 'vitest'
import { createChinaMapOption, createChinaMapScale } from '../chinaMapOptions'
import {
  createLaunchGateOption,
  createTaskStageMatrixOption,
  createTrainingConversionOption,
  createTrainingMixOption,
} from '../constructionOptions'
import { escapeHtml } from '../escapeHtml'
import { createRiskDimensionOption } from '../insightsOptions'
import { createQualityAuditVolumeOption } from '../operationsOptions'
import {
  createBatchProgressOption,
  createCoverageOption,
  createOperationsQualityOption,
  createOverviewCompositionOption,
} from '../panelOptions'
import { createRolloutTrendMatrixOption } from '../rolloutOptions'

const XSS = `<img src=x onerror="alert('xss')">&`
const ESCAPED_XSS = '&lt;img src=x onerror=&quot;alert(&#39;xss&#39;)&quot;&gt;&amp;'

describe('escapeHtml and chart tooltip XSS protection', () => {
  it('escapes all HTML special characters safely', () => {
    expect(escapeHtml(XSS)).toBe(ESCAPED_XSS)
    expect(escapeHtml(null)).toBe('')
    expect(escapeHtml(undefined)).toBe('')
    expect(escapeHtml(42)).toBe('42')
  })

  it('escapes dynamic strings in chart tooltip formatters', () => {
    const mapData = [{ name: XSS, value: 50, total: 1, launched: 1, dual: 0 }]
    const mapOption = createChinaMapOption(mapData, [], [], createChinaMapScale(mapData))
    const mapFormatter = mapOption.tooltip.formatter as (params: Record<string, unknown>) => string
    const mapHtml = mapFormatter({ name: XSS })
    expect(mapHtml).toContain(ESCAPED_XSS)
    expect(mapHtml).not.toContain('<img')

    const scatterHtml = mapFormatter({
      componentType: 'series',
      seriesType: 'effectScatter',
      data: { unitName: XSS, actionText: XSS, province: XSS },
    })
    expect(scatterHtml).toContain(ESCAPED_XSS)
    expect(scatterHtml).not.toContain('<img')

    const gateOption = createLaunchGateOption([
      { name: XSS, completed: 1, inProgress: 1, notStarted: 1, progress: 50 },
    ])
    const gateHtml = (gateOption.tooltip.formatter as (p: unknown) => string)([{ dataIndex: 0 }])
    expect(gateHtml).toContain(ESCAPED_XSS)
    expect(gateHtml).not.toContain('<img')

    const stageOption = createTaskStageMatrixOption([
      { name: XSS, completed: 1, inProgress: 1, notStarted: 1, progress: 50 },
    ])
    const stageHtml = (stageOption.tooltip.formatter as (p: unknown) => string)({
      value: [0, 0, 1],
      data: { percentage: 33.3 },
    })
    expect(stageHtml).toContain(ESCAPED_XSS)
    expect(stageHtml).not.toContain('<img')

    const trainingOption = createTrainingConversionOption([
      { type: XSS, count: 1, expected: 10, actual: 8, passed: 7, cert: 6 },
    ])
    const trainingHtml = (trainingOption.tooltip.formatter as (p: unknown) => string)([{ dataIndex: 0 }])
    expect(trainingHtml).toContain(ESCAPED_XSS)
    expect(trainingHtml).not.toContain('<img')

    const mixOption = createTrainingMixOption([
      { type: XSS, count: 1, expected: 10, actual: 8, passed: 7, cert: 6 },
    ])
    const mixHtml = (mixOption.tooltip.formatter as (p: unknown) => string)({
      name: XSS,
      value: 1,
      percent: 100,
    })
    expect(mixHtml).toContain(ESCAPED_XSS)
    expect(mixHtml).not.toContain('<img')

    const compOption = createOverviewCompositionOption([
      { label: XSS, value: 10, percentage: 100, tone: 'accent' },
    ], 10)
    const compHtml = (compOption.tooltip.formatter as (p: unknown) => string)({ seriesIndex: 0 })
    expect(compHtml).toContain(ESCAPED_XSS)
    expect(compHtml).not.toContain('<img')

    const covOption = createCoverageOption({ covered: 5, gap: 5, rate: 50 })
    const covHtml = (covOption.tooltip.formatter as (p: unknown) => string)({
      name: XSS,
      value: 5,
      percent: 50,
    })
    expect(covHtml).toContain(ESCAPED_XSS)
    expect(covHtml).not.toContain('<img')

    const batchOption = createBatchProgressOption([{ name: XSS, construction: 50, launched: 40 }])
    const batchHtml = (batchOption.tooltip.formatter as (p: unknown) => string)([{ dataIndex: 0 }])
    expect(batchHtml).toContain(ESCAPED_XSS)
    expect(batchHtml).not.toContain('<img')

    const opQualOption = createOperationsQualityOption([
      { name: XSS, value: 99, detail: XSS, tone: 'success' },
    ])
    const opQualHtml = (opQualOption.tooltip.formatter as (p: unknown) => string)([{ dataIndex: 0 }])
    expect(opQualHtml).toContain(ESCAPED_XSS)
    expect(opQualHtml).not.toContain('<img')

    const riskOption = createRiskDimensionOption([
      {
        id: 'danger',
        type: XSS,
        count: 3,
        highCount: 2,
        batchDistribution: { [XSS]: 2 },
        gate: XSS,
        tone: 'danger',
      },
    ], 10)
    const riskHtml = (riskOption.tooltip.formatter as (p: unknown) => string)({ dataIndex: 0 })
    expect(riskHtml).toContain(ESCAPED_XSS)
    expect(riskHtml).not.toContain('<img')

    const rolloutOption = createRolloutTrendMatrixOption([
      { date: XSS, batchId: 1, name: XSS, total: 5, launchedPct: 80, dualPct: 10 },
    ])
    const rolloutHtml = (rolloutOption.tooltip.formatter as (p: unknown) => string)({
      data: { point: { date: XSS, batchId: 1, name: XSS, total: 5, launchedPct: 80, dualPct: 10 } },
    })
    expect(rolloutHtml).toContain(ESCAPED_XSS)
    expect(rolloutHtml).not.toContain('<img')

    const auditOption = createQualityAuditVolumeOption([
      { rule: XSS, total: 100, errors: 0, rate: 100, unit: XSS },
    ])
    const auditHtml = (auditOption.tooltip.formatter as (p: unknown) => string)([{ dataIndex: 0 }])
    expect(auditHtml).toContain(ESCAPED_XSS)
    expect(auditHtml).not.toContain('<img')
  })
})
