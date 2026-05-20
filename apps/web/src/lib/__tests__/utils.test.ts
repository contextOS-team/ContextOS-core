import { afterEach, describe, expect, it, vi } from 'vitest'
import { formatLongRelativeTime } from '../utils'

describe('formatLongRelativeTime', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  function setNow() {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-05-20T12:00:00Z'))
  }

  it('formats 14 hours in the past using long form', () => {
    setNow()
    expect(formatLongRelativeTime('2026-05-19T22:00:00Z')).toBe('14 hours ago')
  })

  it('pluralizes 2 hours', () => {
    setNow()
    expect(formatLongRelativeTime('2026-05-20T10:00:00Z')).toBe('2 hours ago')
  })

  it('singularizes 1 hour', () => {
    setNow()
    expect(formatLongRelativeTime('2026-05-20T11:00:00Z')).toBe('1 hour ago')
  })

  it('formats minutes in long form', () => {
    setNow()
    expect(formatLongRelativeTime('2026-05-20T11:55:00Z')).toBe('5 minutes ago')
  })

  it('formats days in long form', () => {
    setNow()
    expect(formatLongRelativeTime('2026-05-18T12:00:00Z')).toBe('2 days ago')
  })

  it('returns just now for future dates', () => {
    setNow()
    expect(formatLongRelativeTime('2026-05-20T12:01:00Z')).toBe('just now')
  })
})
