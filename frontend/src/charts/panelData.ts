export interface TaskStageDatum {
  name: string
  total: number
  completed: number
  inProgress: number
  notStarted: number
  avgProgress: number
}

export interface RolloutBatchDatum {
  name: string
  total: number
  launched: number
  dual: number
}

export type CompositionTone = 'accent' | 'success' | 'warning' | 'danger' | 'neutral'

export interface CompositionPartInput {
  label: string
  value?: number | string | null
  tone: CompositionTone
}

export function parsePercentage(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? Math.max(0, Math.min(100, parsed)) : null
}

export function buildOverviewComposition(
  total: number | string | null | undefined,
  parts: CompositionPartInput[],
) {
  const values = parts.map((part) => {
    const value = Number(part.value)
    return Number.isFinite(value) ? Math.max(0, value) : 0
  })
  const requestedTotal = Number(total)
  const safeTotal = Number.isFinite(requestedTotal) && requestedTotal > 0
    ? requestedTotal
    : values.reduce((sum, value) => sum + value, 0)

  return {
    total: safeTotal,
    parts: parts.map((part, index) => ({
      ...part,
      value: values[index],
      percentage: safeTotal > 0 ? Math.round((values[index] * 1000) / safeTotal) / 10 : 0,
    })),
  }
}

export function buildTaskStageSeries(stages: TaskStageDatum[]) {
  return stages.map((stage) => ({
    name: stage.name,
    completed: Math.max(0, stage.completed),
    inProgress: Math.max(0, stage.inProgress),
    notStarted: Math.max(0, stage.notStarted),
    progress: Math.max(0, Math.min(100, stage.avgProgress)),
  }))
}

export function buildRolloutComposition(batches: RolloutBatchDatum[]) {
  return batches.map((batch) => ({
    name: batch.name,
    launched: Math.max(0, batch.launched),
    dual: Math.max(0, batch.dual),
    pending: Math.max(0, batch.total - batch.launched - batch.dual),
  }))
}

export function buildCoverageComposition(total?: number | null, covered?: number | null) {
  if (total == null || covered == null || !Number.isFinite(total) || !Number.isFinite(covered) || total <= 0) {
    return null
  }
  const safeCovered = Math.max(0, Math.min(total, covered))
  return {
    covered: safeCovered,
    gap: total - safeCovered,
    rate: Math.round((safeCovered * 10000) / total) / 100,
  }
}

export function buildBatchProgressSeries(batches: Array<{
  name: string
  constructionPct: number | string
  launchedPct: number | string
}>) {
  return batches.map((batch) => ({
    name: batch.name,
    construction: parsePercentage(batch.constructionPct) ?? 0,
    launched: parsePercentage(batch.launchedPct) ?? 0,
  }))
}

export function buildBatchOverviewSeries(batches: Array<{
  name: string
  constructionPct: number | string
  launchedPct: number | string
}>) {
  const list = buildBatchProgressSeries(batches)
  const completed = list.filter((batch) => batch.construction === 100 && batch.launched === 100)
  const active = list.filter((batch) => batch.construction !== 100 || batch.launched !== 100)

  if (completed.length <= 1) return list
  return [
    { name: `已完成${completed.length}批`, construction: 100, launched: 100 },
    ...active,
  ]
}
