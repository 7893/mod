import { describe, it, expect } from 'vitest'
import {
  isRegressionEffective,
  isClassifierEffective,
  isAutomlReady,
} from '../modelEvaluation'

describe('utils/modelEvaluation (KI-023 / KI-028 / KI-034 ADR-0010)', () => {
  describe('isRegressionEffective', () => {
    it('returns true when R² > 0', () => {
      expect(isRegressionEffective(0.4488)).toBe(true)
      expect(isRegressionEffective(0.001)).toBe(true)
      expect(isRegressionEffective(0.85)).toBe(true)
    })

    it('returns false when R² <= 0 (negative R² or zero)', () => {
      expect(isRegressionEffective(0)).toBe(false)
      expect(isRegressionEffective(-0.01)).toBe(false)
      expect(isRegressionEffective(-1.25)).toBe(false)
    })

    it('returns false for null, undefined, NaN, and infinite values', () => {
      expect(isRegressionEffective(null)).toBe(false)
      expect(isRegressionEffective(undefined)).toBe(false)
      expect(isRegressionEffective(Number.NaN)).toBe(false)
      expect(isRegressionEffective(Infinity)).toBe(false)
      expect(isRegressionEffective(-Infinity)).toBe(false)
    })
  })

  describe('isClassifierEffective', () => {
    it('returns true when accuracy is strictly within (0.5, 1.0)', () => {
      expect(isClassifierEffective(0.895)).toBe(true)
      expect(isClassifierEffective(0.51)).toBe(true)
      expect(isClassifierEffective(0.999)).toBe(true)
    })

    it('returns false when accuracy <= 0.5 (chance level or worse)', () => {
      expect(isClassifierEffective(0.5)).toBe(false)
      expect(isClassifierEffective(0.45)).toBe(false)
      expect(isClassifierEffective(0)).toBe(false)
    })

    it('returns false when accuracy == 1.0 (degenerate / label leak)', () => {
      expect(isClassifierEffective(1.0)).toBe(false)
      expect(isClassifierEffective(1.05)).toBe(false)
    })

    it('returns false for null, undefined, and non-finite values', () => {
      expect(isClassifierEffective(null)).toBe(false)
      expect(isClassifierEffective(undefined)).toBe(false)
      expect(isClassifierEffective(Number.NaN)).toBe(false)
    })
  })

  describe('isAutomlReady', () => {
    it('returns true when status is READY and at least one model is effective', () => {
      // Both effective
      expect(isAutomlReady('READY', 0.4488, 0.895)).toBe(true)
      // Regression only effective
      expect(isAutomlReady('READY', 0.4488, 0.5)).toBe(true)
      // Classifier only effective
      expect(isAutomlReady('READY', -0.1, 0.895)).toBe(true)
    })

    it('returns false when status is READY but neither model is effective', () => {
      expect(isAutomlReady('READY', -0.5, 1.0)).toBe(false)
      expect(isAutomlReady('READY', 0, 0.45)).toBe(false)
      expect(isAutomlReady('READY', null, null)).toBe(false)
    })

    it('returns false when status is not READY even if models are effective', () => {
      expect(isAutomlReady('VALIDATION_FAILED', 0.4488, 0.895)).toBe(false)
      expect(isAutomlReady('UNCONFIGURED', 0.4488, 0.895)).toBe(false)
      expect(isAutomlReady('ERROR', 0.4488, 0.895)).toBe(false)
      expect(isAutomlReady(null, 0.4488, 0.895)).toBe(false)
      expect(isAutomlReady(undefined, 0.4488, 0.895)).toBe(false)
    })
  })
})
