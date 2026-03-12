import { describe, it, expect } from 'vitest'
import { computeSyncState } from '../sync-progress'

// ---------------------------------------------------------------------------
// Not syncing — idle state
// ---------------------------------------------------------------------------

describe('computeSyncState: idle', () => {
  it('returns null/false for everything when not syncing', () => {
    const result = computeSyncState({
      isResyncing: false,
      syncProgress: null,
      syncTotal: null,
    })
    expect(result.syncing).toBe(false)
    expect(result.hasTotal).toBe(false)
    expect(result.percent).toBeNull()
    expect(result.label).toBeNull()
  })

  it('ignores stale progress values when not syncing', () => {
    // After a sync finishes, state might still have leftover progress values
    // before they're cleared. isResyncing=false should override.
    const result = computeSyncState({
      isResyncing: false,
      syncProgress: 80,
      syncTotal: 354,
    })
    expect(result.syncing).toBe(false)
    expect(result.percent).toBeNull()
    expect(result.label).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// Phase 1: metadata fetch (syncTotal unknown)
// ---------------------------------------------------------------------------

describe('computeSyncState: phase 1 (metadata fetch)', () => {
  it('syncing=true but percent=null when total is unknown', () => {
    const result = computeSyncState({
      isResyncing: true,
      syncProgress: 0,
      syncTotal: null,
    })
    expect(result.syncing).toBe(true)
    expect(result.hasTotal).toBe(false)
    expect(result.percent).toBeNull()
    expect(result.label).toBe('Fetching pages\u2026')
    expect(result.phaseLabel).toBe('Fetching page metadata\u2026')
  })

  it('treats syncTotal=0 as phase 1 (total not yet known)', () => {
    // Backend briefly sets sync_total=0 before page count is known
    const result = computeSyncState({
      isResyncing: true,
      syncProgress: 0,
      syncTotal: 0,
    })
    expect(result.hasTotal).toBe(false)
    expect(result.percent).toBeNull()
    expect(result.label).toBe('Fetching pages\u2026')
  })

  it('defaults syncProgress to 0 when null', () => {
    const result = computeSyncState({
      isResyncing: true,
      syncProgress: null,
      syncTotal: null,
    })
    expect(result.progress).toBe(0)
  })
})

// ---------------------------------------------------------------------------
// Phase 2: content download (syncTotal known)
// ---------------------------------------------------------------------------

describe('computeSyncState: phase 2 (content download)', () => {
  it('computes correct percentage for normal progress', () => {
    const result = computeSyncState({
      isResyncing: true,
      syncProgress: 80,
      syncTotal: 354,
    })
    expect(result.syncing).toBe(true)
    expect(result.hasTotal).toBe(true)
    expect(result.percent).toBe(23) // Math.round(80/354*100) = 23
    expect(result.label).toBe('80/354 pages')
    expect(result.phaseLabel).toBe('Downloading page content\u2026')
  })

  it('shows 0% at start of phase 2', () => {
    const result = computeSyncState({
      isResyncing: true,
      syncProgress: 0,
      syncTotal: 354,
    })
    expect(result.percent).toBe(0)
    expect(result.label).toBe('0/354 pages')
  })

  it('shows 100% when complete', () => {
    const result = computeSyncState({
      isResyncing: true,
      syncProgress: 354,
      syncTotal: 354,
    })
    expect(result.percent).toBe(100)
  })

  // BUG FIX: syncProgress can exceed syncTotal due to the pages_count fallback
  // in the polling code. Percent must clamp to 100.
  it('clamps to 100% when progress exceeds total (race condition)', () => {
    const result = computeSyncState({
      isResyncing: true,
      syncProgress: 400,
      syncTotal: 354,
    })
    expect(result.percent).toBe(100)
    expect(result.label).toBe('400/354 pages') // label shows raw values for debugging
  })

  it('clamps to 0% for negative progress (defensive)', () => {
    const result = computeSyncState({
      isResyncing: true,
      syncProgress: -5,
      syncTotal: 354,
    })
    expect(result.percent).toBe(0)
  })

  it('handles syncProgress=null during phase 2 (backend race)', () => {
    // Backend sets sync_total before sync_progress starts incrementing
    const result = computeSyncState({
      isResyncing: true,
      syncProgress: null,
      syncTotal: 354,
    })
    expect(result.progress).toBe(0)
    expect(result.percent).toBe(0)
    expect(result.label).toBe('0/354 pages')
  })
})

// ---------------------------------------------------------------------------
// Edge cases
// ---------------------------------------------------------------------------

describe('computeSyncState: edge cases', () => {
  it('single page sync', () => {
    const result = computeSyncState({
      isResyncing: true,
      syncProgress: 1,
      syncTotal: 1,
    })
    expect(result.percent).toBe(100)
    expect(result.label).toBe('1/1 pages')
  })

  it('negative syncTotal treated as no total', () => {
    // Should never happen, but defensive
    const result = computeSyncState({
      isResyncing: true,
      syncProgress: 5,
      syncTotal: -1,
    })
    expect(result.hasTotal).toBe(false)
    expect(result.percent).toBeNull()
  })
})
