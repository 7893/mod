import type { EntityRow } from '../stores/project.ts'

export interface CountedOption {
  value: string
  label: string
}

export const ALL = '全部'

/** 省级行政区展示顺序（华北→东北→华东→中南→西南→西北→港澳台）。 */
export const NATIONAL_PROVINCE_ORDER = [
  '北京', '天津', '河北', '山西', '内蒙古',
  '辽宁', '吉林', '黑龙江',
  '上海', '江苏', '浙江', '安徽', '福建', '江西', '山东',
  '河南', '湖北', '湖南', '广东', '广西', '海南',
  '重庆', '四川', '贵州', '云南', '西藏',
  '陕西', '甘肃', '青海', '宁夏', '新疆',
  '香港', '澳门', '台湾',
] as const

export const BATCH_ORDER = ['第一批', '第二批', '第三批', '第四批', '第五批', '第六批', '第七批', '第八批'] as const
export const STATUS_ORDER = ['未启动', '准备中', '建设中', '双轨运行', '已上线'] as const
export const READINESS_ORDER = ['已导入', '已校验', '收集中', '未收集'] as const

interface CountedOptionsConfig {
  /** 固定顺序；不在顺序表中的值追加在后。 */
  order: readonly string[]
  /** 「全部」项文案，例如 `全部省份`。 */
  allLabel: string
  /** 顺序表中计数为 0 的值是否仍然列出（状态筛选需要，省份/批次不需要）。 */
  includeZero?: boolean
  /** 「全部」项括号内的计数；默认为行数。 */
  allCount?: (rows: readonly EntityRow[], counts: Map<string, number>) => number
  /** 「全部」项计数后缀，默认 `家`。 */
  allSuffix?: string
}

/** 为下拉筛选构造带计数的选项列表：`值 (N家)`。 */
export function countedOptions(
  rows: readonly EntityRow[],
  pick: (row: EntityRow) => string | null | undefined,
  config: CountedOptionsConfig,
): CountedOption[] {
  const counts = new Map<string, number>()
  for (const row of rows) {
    const key = pick(row)
    if (key) counts.set(key, (counts.get(key) || 0) + 1)
  }
  const ordered = config.order
    .filter((value) => config.includeZero || counts.has(value))
    .map((value) => ({ value, label: `${value} (${counts.get(value) || 0}家)` }))
  const remaining = [...counts.keys()]
    .filter((value) => !config.order.includes(value))
    .map((value) => ({ value, label: `${value} (${counts.get(value)}家)` }))
  const allCount = config.allCount ? config.allCount(rows, counts) : rows.length
  return [
    { value: ALL, label: `${config.allLabel} (${allCount}${config.allSuffix ?? '家'})` },
    ...ordered,
    ...remaining,
  ]
}

/** 单一「全部」值匹配。 */
export function matchesOption(selected: string, actual: string | null | undefined): boolean {
  return selected === ALL || actual === selected
}

/** 台账关键字：单位名 / 联系人 / 省份 / 批次 / 数字 ID / MOD-ID，大小写宽容。 */
export function matchesEntityQuery(row: EntityRow, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  return (
    row.name.toLowerCase().includes(q) ||
    row.owner.toLowerCase().includes(q) ||
    row.province.toLowerCase().includes(q) ||
    row.batch.toLowerCase().includes(q) ||
    String(row.id).includes(q) ||
    `mod-${row.id}`.includes(q)
  )
}
