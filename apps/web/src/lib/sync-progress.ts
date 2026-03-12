/**
 * Shared utility for computing sync state from progress values.
 * Used by integration sync sections (Notion, etc.) to derive
 * syncing status, percentage, and label for the UI.
 */

interface SyncInput {
  isResyncing: boolean
  syncProgress: number | null
  syncTotal: number | null
}

interface SyncState {
  syncing: boolean
  percent: number | null
  label: string | null
}

export function computeSyncState({ isResyncing, syncProgress, syncTotal }: SyncInput): SyncState {
  if (!isResyncing) {
    return { syncing: false, percent: null, label: null }
  }

  if (syncProgress == null || syncTotal == null || syncTotal === 0) {
    return { syncing: true, percent: null, label: 'Syncing...' }
  }

  const percent = Math.round((syncProgress / syncTotal) * 100)
  const label = `${syncProgress} / ${syncTotal}`

  return { syncing: true, percent, label }
}
