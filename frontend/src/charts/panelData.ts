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
