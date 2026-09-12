export function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return '—'
  return new Intl.NumberFormat('zh-CN').format(Number(value))
}

export function formatPercent(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return '—'
  return `${Number(value).toFixed(decimals).replace(/\.00$/, '').replace(/(\.\d)0$/, '$1')}%`
}

/**
 * 统一日期时间展示：`YYYY-MM-DD HH:mm[:ss]`，24 小时制。
 * 可指定展示时区（顶栏时钟跟随后端 `meta.displayTimezone`）。
 */
export function formatDateTime(
  value: Date | string | number | null | undefined,
  options: { seconds?: boolean; timeZone?: string } = {},
): string {
  if (value === null || value === undefined || value === '') return '—'
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: options.timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: options.seconds ? '2-digit' : undefined,
    hour12: false,
  }).formatToParts(date)
  const map: Record<string, string> = {}
  for (const part of parts) map[part.type] = part.value
  const time = `${map.hour}:${map.minute}${options.seconds ? `:${map.second}` : ''}`
  return `${map.year}-${map.month}-${map.day} ${time}`
}

/**
 * 分段格式化月日与时间：不显示年份，仅展示月日与时分秒
 */
export function formatDateParts(
  value: Date | string | number | null | undefined,
  options: { seconds?: boolean; timeZone?: string } = {},
): { date: string; time: string; full: string } {
  if (value === null || value === undefined || value === '') return { date: '', time: '—', full: '—' }
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return { date: '', time: String(value), full: String(value) }
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: options.timeZone,
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: options.seconds ? '2-digit' : undefined,
    hour12: false,
  }).formatToParts(date)
  const map: Record<string, string> = {}
  for (const part of parts) map[part.type] = part.value
  const dateStr = `${map.month}-${map.day}`
  const timeStr = `${map.hour}:${map.minute}${options.seconds ? `:${map.second}` : ''}`
  return { date: dateStr, time: timeStr, full: `${dateStr} ${timeStr}` }
}

