export const STALE_WORKSPACE_UPDATE_MS = 6 * 60 * 60 * 1000

export function isWorkspaceUpdateStale(
  lastUpdatedAt: Date | null,
  now: Date = new Date()
): boolean {
  if (!lastUpdatedAt) return false
  const lastUpdatedMs = lastUpdatedAt.getTime()
  return Number.isFinite(lastUpdatedMs)
    && now.getTime() - lastUpdatedMs > STALE_WORKSPACE_UPDATE_MS
}
