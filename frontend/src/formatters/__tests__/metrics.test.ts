import { describe, it, expect } from 'vitest'
import { formatCount, formatPercent } from '../metrics'

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
