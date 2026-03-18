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
      if (meta.error) return `${meta.integration ?? 'Unknown'} sync failed`
      return `${meta.integration ?? 'Unknown'} sync completed`
    case 'context_generated':
      if (meta.error)
        return `Context generation failed${meta.ticket_id ? ` for ${meta.ticket_id}` : ''}`
      if (meta.ticket_id)
        return `Context generated for ${meta.ticket_id} \u00b7 ${meta.source_count ?? '?'} sources`
      return `Context generated from ${meta.source_count ?? '?'} sources`
    case 'integration_connected':
      return `${meta.integration ?? 'Unknown'} connected`
    case 'integration_disconnected':
      return `${meta.integration ?? 'Unknown'} disconnected`
    case 'ticket_created':
      return `New ticket: ${meta.ticket_id ?? ''} ${meta.title ?? ''}`.trim()
    case 'pr_merged':
      return `PR merged: ${meta.repo ?? ''}#${meta.pr_number ?? ''} ${meta.title ?? ''}`.trim()
    case 'meeting_recorded':
      return `Meeting recorded: ${meta.title ?? 'Untitled'}`
    case 'page_created':
      return `New page: ${meta.page_title ?? 'Untitled'}`
    case 'messages_digest': {
      const integration = meta.integration ?? 'Messages'
      const count = typeof meta.message_count === 'number' ? meta.message_count : 0
      const channels = typeof meta.channels_active === 'number' ? meta.channels_active : 0
      return `${integration} digest — ${count} messages, ${channels} channel${channels === 1 ? '' : 's'}`
    }
    default:
      return 'Unknown event'
  }
}

/**
 * Extract a subtitle line for richer event rows, or null if none applies.
 */
export function getEventSubtitle(event: ActivityEvent): string | null {
  const meta = event.metadata

  switch (event.event_type) {
    case 'sync_completed':
      if (meta.error && typeof meta.error_message === 'string')
        return meta.error_message.slice(0, 80)
      return null
    case 'context_generated':
      if (meta.source_count)
        return `${meta.source_count} sources · ${formatTokenCount(meta.token_count)}`
      return null
    case 'ticket_created':
      return meta.ticket_id ? `${meta.integration ?? ''} ${meta.ticket_id}`.trim() : null
    case 'pr_merged':
      return meta.repo ? `${meta.repo}#${meta.pr_number ?? ''}` : null
    case 'meeting_recorded':
      if (typeof meta.duration_minutes === 'number')
        return `${meta.duration_minutes} min`
      return null
    // messages_digest: DigestRow reads metadata directly, not via getEventSubtitle
    default:
      return null
  }
}

function formatTokenCount(count: unknown): string {
  if (typeof count !== 'number') return ''
  return count >= 1000 ? `${(count / 1000).toFixed(1)}k tokens` : `${count} tokens`
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
