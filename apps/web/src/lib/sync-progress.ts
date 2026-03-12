/**
 * Pure computation helpers for sync progress UI.
 *
 * Extracted so they can be unit-tested without a DOM.
 */

export interface SyncState {
  isResyncing: boolean
  syncProgress: number | null
  syncTotal: number | null
}

export interface ComputedSync {
  /** Whether a sync operation is actively running (any phase). */
  syncing: boolean
  /** Whether we're in phase 2 (have a known total > 0). */
  hasTotal: boolean
  /** Current progress value, defaulting to 0 when null. */
  progress: number
  /** Percentage 0–100, or null when total is unknown (phase 1). */
  percent: number | null
  /** Short header label, or null when not syncing. */
  label: string | null
  /** Phase description for the expanded view. */
  phaseLabel: string
}

export function computeSyncState(state: SyncState): ComputedSync {
  const { isResyncing, syncProgress, syncTotal } = state
  const hasTotal = isResyncing && syncTotal != null && syncTotal > 0
  const progress = syncProgress ?? 0

  const percent = hasTotal
    ? Math.max(0, Math.min(100, Math.round((progress / syncTotal!) * 100)))
    : null

  const label = isResyncing
    ? hasTotal
      ? `${progress}/${syncTotal} pages`
      : 'Fetching pages\u2026'
    : null

  const phaseLabel = hasTotal
    ? 'Downloading page content\u2026'
    : 'Fetching page metadata\u2026'

  return { syncing: isResyncing, hasTotal, progress, percent, label, phaseLabel }
}
