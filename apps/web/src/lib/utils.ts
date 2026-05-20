import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Formats an ISO date string as a human-readable relative time.
 * Returns "just now" for times less than a minute ago,
 * or "{n}m/h/d ago" for longer durations.
 */
export function formatRelativeTime(isoDate: string): string {
  // "YYYY-MM-DD" without time → JS parses as UTC midnight. Append T00:00:00
  // so it's treated as local midnight instead.
  const date = new Date(/^\d{4}-\d{2}-\d{2}$/.test(isoDate) ? isoDate + 'T00:00:00' : isoDate)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  if (diffMs < 0) return 'just now'
  const diffMin = Math.floor(diffMs / 60_000)
  const diffHours = Math.floor(diffMin / 60)
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays > 0) return `${diffDays}d ago`
  if (diffHours > 0) return `${diffHours}h ago`
  if (diffMin > 0) return `${diffMin}m ago`
  return 'just now'
}

/**
 * Filters out external IDs that aren't human-readable display names.
 * Returns null for UUIDs and workspace ID patterns.
 */
export function displayName(name: string | null | undefined): string | null {
  if (!name) return null
  if (/^[0-9a-f]{8}-/i.test(name)) return null
  if (/^[A-Z][A-Z0-9]{6,}$/.test(name)) return null
  return name
}

/**
 * Formats an ISO date string as a LONG-form human-readable relative time
 * ("14 hours ago", "2 days ago", "5 minutes ago", "1 hour ago").
 *
 * Distinct from {@link formatRelativeTime} which returns SHORT form
 * ("14h ago", "2d ago"). Both helpers must coexist:
 *  - Short form is used by activity timelines / dense lists.
 *  - Long form is used by the Phase 41 dashboard headline subtext
 *    per CONTEXT.md §4 (examples: "since you last looked, 14 hours ago").
 *
 * CONTEXT.md §4 is the contract source for the long form. Do NOT replace
 * usages of formatLongRelativeTime in headline-rules.ts with the short helper —
 * the headline subtext requires the long form.
 *
 * @param isoDate ISO-8601 timestamp string.
 * @returns "just now" if the date is in the future or under 1 minute ago,
 *          otherwise a long-form English phrase with correct singular/plural.
 */
export function formatLongRelativeTime(isoDate: string): string {
  const date = new Date(/^\d{4}-\d{2}-\d{2}$/.test(isoDate) ? isoDate + 'T00:00:00' : isoDate)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  if (diffMs < 0) return 'just now'
  const diffMin = Math.floor(diffMs / 60_000)
  const diffHours = Math.floor(diffMin / 60)
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays > 0) return `${diffDays} ${diffDays === 1 ? 'day' : 'days'} ago`
  if (diffHours > 0) return `${diffHours} ${diffHours === 1 ? 'hour' : 'hours'} ago`
  if (diffMin > 0) return `${diffMin} ${diffMin === 1 ? 'minute' : 'minutes'} ago`
  return 'just now'
}
