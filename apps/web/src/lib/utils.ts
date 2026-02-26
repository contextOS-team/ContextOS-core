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
  const date = new Date(isoDate)
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
