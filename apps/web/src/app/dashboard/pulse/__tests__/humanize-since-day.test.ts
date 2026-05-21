import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { humanizeSinceDay } from '../use-dashboard-data'

const WEEKDAY_RE = /^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)$/
const SHORT_WEEKDAY_RE = /^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)$/

describe('humanizeSinceDay', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-05-20T12:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns a full weekday for a one-day-old item', () => {
    const result = humanizeSinceDay(new Date('2026-05-19T12:00:00Z'))

    expect(result).toBe('Tuesday')
    expect(result.length).toBeGreaterThan(3)
    expect(result).toMatch(WEEKDAY_RE)
    expect(result).not.toMatch(SHORT_WEEKDAY_RE)
  })

  it('returns a full weekday for a two-day-old item', () => {
    const result = humanizeSinceDay(new Date('2026-05-18T12:00:00Z'))

    expect(result).toBe('Monday')
    expect(result.length).toBeGreaterThan(3)
    expect(result).toMatch(WEEKDAY_RE)
    expect(result).not.toMatch(SHORT_WEEKDAY_RE)
  })

  it('returns a full weekday for a six-day-old item', () => {
    const result = humanizeSinceDay(new Date('2026-05-14T12:00:00Z'))

    expect(result.length).toBeGreaterThan(3)
    expect(result).toMatch(WEEKDAY_RE)
    expect(result).not.toMatch(SHORT_WEEKDAY_RE)
  })

  it('returns an absolute date outside the seven-day window', () => {
    const result = humanizeSinceDay(new Date('2026-05-12T12:00:00Z'))

    expect(result).toBe('May 12')
    expect(result).toMatch(/^[A-Z][a-z]{2} \d+$/)
    expect(result).not.toMatch(WEEKDAY_RE)
  })

  it('returns an absolute date for future dates', () => {
    expect(humanizeSinceDay(new Date('2026-05-21T12:00:00Z'))).toBe('May 21')
  })
})
