import { describe, it, expect } from 'vitest'
import { formatCount, formatDateTime, formatDateParts, formatPercent } from '../metrics'

describe('formatters/metrics', () => {
  describe('formatCount', () => {
    it('returns em-dash for null, undefined, NaN, or non-finite values', () => {
      expect(formatCount(null)).toBe('—')
      expect(formatCount(undefined)).toBe('—')
      expect(formatCount(Number.NaN)).toBe('—')
      expect(formatCount(Infinity)).toBe('—')
      expect(formatCount(-Infinity)).toBe('—')
    })

    it('formats zero correctly as string 0', () => {
      expect(formatCount(0)).toBe('0')
    })

    it('formats regular and large integers with zh-CN grouping separators', () => {
      expect(formatCount(100)).toBe('100')
      expect(formatCount(1234)).toBe('1,234')
      expect(formatCount(1000000)).toBe('1,000,000')
      expect(formatCount(31838078)).toBe('31,838,078')
    })

    it('formats negative integers properly', () => {
      expect(formatCount(-500)).toBe('-500')
      expect(formatCount(-12345)).toBe('-12,345')
    })
  })

  describe('formatPercent', () => {
    it('returns em-dash for null, undefined, NaN, or non-finite values', () => {
      expect(formatPercent(null)).toBe('—')
      expect(formatPercent(undefined)).toBe('—')
      expect(formatPercent(Number.NaN)).toBe('—')
      expect(formatPercent(Infinity)).toBe('—')
      expect(formatPercent(-Infinity)).toBe('—')
    })

    it('formats 0 and 100 percentages cleanly without trailing zeros', () => {
      expect(formatPercent(0)).toBe('0%')
      expect(formatPercent(100)).toBe('100%')
      expect(formatPercent(50)).toBe('50%')
    })

    it('trims trailing zeros after decimal point', () => {
      expect(formatPercent(99.5)).toBe('99.5%')
      expect(formatPercent(88.0)).toBe('88%')
      expect(formatPercent(88.75)).toBe('88.75%')
    })

    it('respects custom decimals argument', () => {
      expect(formatPercent(12.3456, 1)).toBe('12.3%')
      expect(formatPercent(12.3456, 3)).toBe('12.346%')
      expect(formatPercent(12.3456, 0)).toBe('12%')
    })

    it('formats negative percentages correctly', () => {
      expect(formatPercent(-4.5)).toBe('-4.5%')
      expect(formatPercent(-10.0)).toBe('-10%')
    })
  })
})

describe('formatDateTime', () => {
  const instant = new Date('2026-09-09T14:05:09Z')

  it('renders 24h date-time in the given timezone, optionally with seconds', () => {
    expect(formatDateTime(instant, { timeZone: 'Asia/Shanghai' })).toBe('2026-09-09 22:05')
    expect(formatDateTime(instant, { timeZone: 'Asia/Shanghai', seconds: true })).toBe('2026-09-09 22:05:09')
    expect(formatDateTime(instant.toISOString(), { timeZone: 'UTC' })).toBe('2026-09-09 14:05')
  })

  it('degrades gracefully on empty or unparsable input', () => {
    expect(formatDateTime(null)).toBe('—')
    expect(formatDateTime('')).toBe('—')
    expect(formatDateTime('not-a-date')).toBe('not-a-date')
  })
})

describe('formatDateParts', () => {
  const instant = new Date('2026-09-09T14:05:09Z')

  it('splits month-day and time without year', () => {
    expect(formatDateParts(instant, { timeZone: 'Asia/Shanghai', seconds: true })).toEqual({
      date: '09-09',
      time: '22:05:09',
      full: '09-09 22:05:09',
    })
  })

  it('degrades gracefully on empty input', () => {
    expect(formatDateParts(null)).toEqual({ date: '', time: '—', full: '—' })
    expect(formatDateParts('')).toEqual({ date: '', time: '—', full: '—' })
  })
})

