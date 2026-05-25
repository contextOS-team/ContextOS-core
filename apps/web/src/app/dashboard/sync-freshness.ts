export const STALE_WORKSPACE_UPDATE_MS = 6 * 60 * 60 * 1000

export function parseWorkspaceSyncDate(value?: string | null): Date | null {
  if (!value) return null
  const normalized = /(?:z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`
  const date = new Date(normalized)
  return Number.isFinite(date.getTime()) ? date : null
}

export function isWorkspaceUpdateStale(
  lastUpdatedAt: Date | null,
  now: Date = new Date()
): boolean {
  if (!lastUpdatedAt) return false
  const lastUpdatedMs = lastUpdatedAt.getTime()
  return Number.isFinite(lastUpdatedMs)
    && now.getTime() - lastUpdatedMs > STALE_WORKSPACE_UPDATE_MS
}
