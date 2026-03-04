import type { ActivityEvent } from './types'

/**
 * Produce an impersonal description for an activity event.
 * Uses metadata.integration for integration-related events with "Unknown" fallback.
 */
export function formatEventDescription(event: ActivityEvent): string {
  const meta = event.metadata

  switch (event.event_type) {
    case 'sync_started':
      return `${meta.integration ?? 'Unknown'} sync started`
    case 'sync_completed':
      return `${meta.integration ?? 'Unknown'} sync completed`
    case 'context_generated':
      return `Context generated from ${meta.source_count ?? '?'} sources`
    case 'integration_connected':
      return `${meta.integration ?? 'Unknown'} connected`
    case 'integration_disconnected':
      return `${meta.integration ?? 'Unknown'} disconnected`
    case 'user_signed_up':
      return 'Workspace created'
    default:
      return 'Unknown event'
  }
}

/**
 * Extract a single metadata chip string for display, or null if none applies.
 * sync_completed prioritizes items_count over duration_ms.
 * context_generated shows token count (k format for 1000+).
 */
export function getMetadataChip(event: ActivityEvent): string | null {
  const meta = event.metadata

  switch (event.event_type) {
    case 'sync_completed':
      if (typeof meta.items_count === 'number')
        return `${meta.items_count} items`
      if (typeof meta.duration_ms === 'number')
        return `${(meta.duration_ms / 1000).toFixed(1)}s`
      return null
    case 'context_generated':
      if (typeof meta.token_count === 'number') {
        return meta.token_count >= 1000
          ? `${(meta.token_count / 1000).toFixed(1)}k tokens`
          : `${meta.token_count} tokens`
      }
      return null
    default:
      return null
  }
}

/**
 * Format a timestamp for inline display in the timeline.
 * < 1 min: "just now"
 * 1-59 min: "{n}m ago"
 * 1-23 hours: "{n}h ago"
 * 24+ hours: absolute time "3:42 PM" (day header provides date context)
 */
export function formatTimelineTimestamp(isoDate: string): string {
  const date = new Date(isoDate)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()

  if (diffMs < 0) return 'just now'

  const diffMin = Math.floor(diffMs / 60_000)
  const diffHours = Math.floor(diffMin / 60)

  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  if (diffHours < 24) return `${diffHours}h ago`

  // 24h+: absolute time (day header provides date context)
  return date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
}

/**
 * Format a full timestamp for hover tooltips.
 * Output: "Feb 28, 2026 at 3:42 PM"
 */
export function formatFullTimestamp(isoDate: string): string {
  const date = new Date(isoDate)
  return (
    date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    }) +
    ' at ' +
    date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    })
  )
}

/**
 * Format a day group label for timeline headers.
 * TODAY / YESTERDAY / weekday uppercase (7 days) / "FEB 24, 2026" (older)
 * Uses midnight-aligned date comparison.
 */
export function formatDayLabel(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const target = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const diffDays = Math.floor(
    (today.getTime() - target.getTime()) / 86_400_000
  )

  if (diffDays === 0) return 'TODAY'
  if (diffDays === 1) return 'YESTERDAY'
  if (diffDays < 7) {
    return target
      .toLocaleDateString('en-US', { weekday: 'long' })
      .toUpperCase()
  }

  // Older: "FEB 24, 2026"
  return target
    .toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
    .toUpperCase()
}

/**
 * Group chronologically sorted events into day buckets.
 * Returns an array of { label, date (YYYY-MM-DD), events } preserving input order.
 */
export function groupEventsByDay(
  events: ActivityEvent[]
): Array<{ label: string; date: string; events: ActivityEvent[] }> {
  if (events.length === 0) return []

  const groups: Map<string, ActivityEvent[]> = new Map()

  for (const event of events) {
    const d = new Date(event.created_at)
    const dateKey = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

    if (!groups.has(dateKey)) {
      groups.set(dateKey, [])
    }
    groups.get(dateKey)!.push(event)
  }

  return Array.from(groups.entries()).map(([dateKey, dayEvents]) => ({
    label: formatDayLabel(dayEvents[0].created_at),
    date: dateKey,
    events: dayEvents,
  }))
}
