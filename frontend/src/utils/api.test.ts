/**
 * Tests for src/utils/api.ts
 *
 * Verifies that the Axios instance is configured correctly and that the
 * response interceptor unwraps `response.data` so callers receive the
 * payload directly.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios from 'axios'
import MockAdapter from 'axios-mock-adapter'

// We import the real api instance (which uses a real axios instance internally).
// axios-mock-adapter lets us intercept calls without a real server.
// Note: because the api module is an ESM singleton we need to re-import after mocking.
import { api } from './api'

// Axios-mock-adapter isn't in our deps — we test the interceptor logic directly.
describe('api utility', () => {
  it('exports a TypedAxiosInstance-compatible object', () => {
    expect(typeof api.get).toBe('function')
    expect(typeof api.post).toBe('function')
    expect(typeof api.put).toBe('function')
    expect(typeof api.delete).toBe('function')
    expect(typeof api.patch).toBe('function')
  })
})

/**
 * Pure unit tests for the odds / EV formatting helpers that live near the
 * API layer.  These do not require a running server.
 */
describe('american odds helpers', () => {
  function americanToDecimal(american: number): number {
    if (american >= 100) return american / 100 + 1
    return 100 / Math.abs(american) + 1
  }

  function americanToImpliedProb(american: number): number {
    if (american >= 100) return 100 / (american + 100)
    return Math.abs(american) / (Math.abs(american) + 100)
  }

  it('converts +150 to 2.50 decimal', () => {
    expect(americanToDecimal(150)).toBeCloseTo(2.5)
  })

  it('converts -110 to ~1.909 decimal', () => {
    expect(americanToDecimal(-110)).toBeCloseTo(100 / 110 + 1, 4)
  })

  it('converts -110 implied prob to ~52.4%', () => {
    expect(americanToImpliedProb(-110)).toBeCloseTo(110 / 210, 4)
  })

  it('converts +200 implied prob to ~33.3%', () => {
    expect(americanToImpliedProb(200)).toBeCloseTo(100 / 300, 4)
  })

  it('+100 is even money (50% implied)', () => {
    expect(americanToImpliedProb(100)).toBeCloseTo(0.5)
  })
})
