import { describe, expect, it } from 'vitest'
import {
  aggregateSelectedProvinces,
  hasProvinceMultiSelectModifier,
  toggleProvinceSelection,
} from '../provinceSelection.ts'

describe('province selection', () => {
  it('uses ordinary clicks as single selection and toggles the active province back to nationwide', () => {
    expect(toggleProvinceSelection([], '广东', false)).toEqual(['广东'])
    expect(toggleProvinceSelection(['广东', '江苏'], '江苏', false)).toEqual(['江苏'])
    expect(toggleProvinceSelection(['江苏'], '江苏', false)).toEqual([])
  })

  it('uses modified clicks to add or remove provinces', () => {
    expect(toggleProvinceSelection(['广东'], '江苏', true)).toEqual(['广东', '江苏'])
    expect(toggleProvinceSelection(['广东', '江苏'], '广东', true)).toEqual(['江苏'])
    expect(toggleProvinceSelection(['江苏'], '江苏', true)).toEqual([])
  })

  it('recognizes Ctrl and Command through the ECharts pointer event wrapper', () => {
    expect(hasProvinceMultiSelectModifier({ ctrlKey: true })).toBe(true)
    expect(hasProvinceMultiSelectModifier({ event: { metaKey: true } })).toBe(true)
    expect(hasProvinceMultiSelectModifier({ event: {} })).toBe(false)
  })

  it('sums counts and weights construction progress by included organizations', () => {
    const aggregate = aggregateSelectedProvinces([
      { name: '广东', value: 40, total: 10, launched: 6, dual: 2 },
      { name: '江苏', value: 80, total: 30, launched: 20, dual: 4 },
      { name: '浙江', value: 100, total: 50, launched: 50, dual: 0 },
    ], ['广东', '江苏'])

    expect(aggregate).toEqual({
      total: 40,
      launched: 26,
      dual: 6,
      progress: 70,
    })
    expect(aggregateSelectedProvinces([], [])).toBeNull()
  })
})
