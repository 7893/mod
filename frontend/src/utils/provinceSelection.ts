export interface ProvinceSelectionDatum {
  name: string
  value: number
  constructionPct?: number
  total: number
  launched: number
  dual: number
}

export interface ProvinceSelectionAggregate {
  total: number
  launched: number
  dual: number
  progress: number
}

export interface ProvinceSelectionModifierEvent {
  ctrlKey?: boolean
  metaKey?: boolean
  event?: ProvinceSelectionModifierEvent
}

export function hasProvinceMultiSelectModifier(event?: ProvinceSelectionModifierEvent): boolean {
  const pointerEvent = event?.event ?? event
  return Boolean(pointerEvent?.ctrlKey || pointerEvent?.metaKey)
}

export function toggleProvinceSelection(
  current: readonly string[],
  province: string,
  additive: boolean,
): string[] {
  if (!additive) {
    return current.length === 1 && current[0] === province ? [] : [province]
  }

  return current.includes(province)
    ? current.filter(item => item !== province)
    : [...current, province]
}

export function aggregateSelectedProvinces(
  data: readonly ProvinceSelectionDatum[],
  selected: readonly string[],
): ProvinceSelectionAggregate | null {
  if (selected.length === 0) return null

  const selectedNames = new Set(selected)
  let total = 0
  let launched = 0
  let dual = 0
  let weightedProgress = 0

  for (const item of data) {
    if (!selectedNames.has(item.name)) continue
    const itemTotal = Number(item.total) || 0
    const itemProgress = Number(item.constructionPct ?? item.value) || 0
    total += itemTotal
    launched += Number(item.launched) || 0
    dual += Number(item.dual) || 0
    weightedProgress += itemProgress * itemTotal
  }

  return {
    total,
    launched,
    dual,
    progress: total > 0 ? weightedProgress / total : 0,
  }
}
