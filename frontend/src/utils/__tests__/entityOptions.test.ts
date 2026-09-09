import { describe, it, expect } from 'vitest'
import type { EntityRow } from '../../stores/project'
import { ALL, BATCH_ORDER, STATUS_ORDER, countedOptions, matchesEntityQuery, matchesOption } from '../entityOptions'

function row(partial: Partial<EntityRow>): EntityRow {
  return {
    id: 1,
    name: '示例单位',
    province: '北京',
    batch: '第一批',
    owner: '张三',
    status: '双轨运行',
    construction: 50,
    openingData: 20,
    ...partial,
  } as EntityRow
}

const rows = [
  row({ id: 1, province: '广东', batch: '第二批', status: '双轨运行' }),
  row({ id: 2, province: '北京', batch: '第一批', status: '已上线' }),
  row({ id: 3, province: '广东', batch: '第二批', status: '双轨运行' }),
  row({ id: 4, province: '火星', batch: '第二批', status: '双轨运行' }),
]

describe('countedOptions', () => {
  it('orders known values, appends unknown ones and drops zero counts by default', () => {
    const opts = countedOptions(rows, (r) => r.batch, { order: BATCH_ORDER, allLabel: '全部批次' })
    expect(opts.map((o) => o.value)).toEqual([ALL, '第一批', '第二批'])
    expect(opts[0].label).toBe('全部批次 (4家)')
    expect(opts[2].label).toBe('第二批 (3家)')
  })

  it('keeps zero-count entries when includeZero is set and lists unknown values last', () => {
    const opts = countedOptions(rows, (r) => r.status, { order: STATUS_ORDER, allLabel: '全部状态', includeZero: true })
    expect(opts.map((o) => o.value)).toEqual([ALL, ...STATUS_ORDER])
    expect(opts.find((o) => o.value === '未启动')?.label).toBe('未启动 (0家)')
    const provinces = countedOptions(rows, (r) => r.province, { order: ['北京', '广东'], allLabel: '全部省份' })
    expect(provinces.at(-1)?.value).toBe('火星')
  })

  it('supports a custom all-count and suffix for sparse fields', () => {
    const sparse = [row({ readinessStatus: '已导入' }), row({ readinessStatus: undefined })]
    const opts = countedOptions(sparse, (r) => r.readinessStatus, {
      order: ['已导入'],
      allLabel: '全部准备度',
      allCount: (_r, counts) => [...counts.values()].reduce((a, b) => a + b, 0),
      allSuffix: '家有数据',
    })
    expect(opts[0].label).toBe('全部准备度 (1家有数据)')
  })
})

describe('matchers', () => {
  it('matchesOption treats ALL as wildcard', () => {
    expect(matchesOption(ALL, '任意')).toBe(true)
    expect(matchesOption('北京', '北京')).toBe(true)
    expect(matchesOption('北京', '广东')).toBe(false)
  })

  it('matchesEntityQuery searches name, owner, province, batch and MOD id case-insensitively', () => {
    const r = row({ id: 42, name: 'Alpha 单位', owner: '李四' })
    expect(matchesEntityQuery(r, '')).toBe(true)
    expect(matchesEntityQuery(r, 'alpha')).toBe(true)
    expect(matchesEntityQuery(r, '李四')).toBe(true)
    expect(matchesEntityQuery(r, 'MOD-42')).toBe(true)
    expect(matchesEntityQuery(r, '第一批')).toBe(true)
    expect(matchesEntityQuery(r, '不存在')).toBe(false)
  })
})
