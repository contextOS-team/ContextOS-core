import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { ActivityEvent } from '../types'
import {
  formatEventDescription,
  getEventSubtitle,
  formatTimelineTimestamp,
  formatFullTimestamp,
  formatDayLabel,
  groupEventsByDay,
} from '../formatters'

// Helper to create a mock event
function mockEvent(
  overrides: Partial<ActivityEvent> = {}
): ActivityEvent {
  return {
    id: 'evt-1',
    workspace_id: 'ws-1',
    actor_id: null,
    event_type: 'sync_started',
    metadata: {},
    created_at: new Date().toISOString(),
    ...overrides,
  }
}

describe('formatEventDescription', () => {
  it('sync_started with integration metadata returns "{integration} sync started"', () => {
    const event = mockEvent({
      event_type: 'sync_started',
      metadata: { integration: 'Linear' },
    })
    expect(formatEventDescription(event)).toBe('Linear sync started')
  })

  it('sync_completed with integration metadata returns "{integration} sync completed"', () => {
    const event = mockEvent({
      event_type: 'sync_completed',
      metadata: { integration: 'Slack' },
    })
    expect(formatEventDescription(event)).toBe('Slack sync completed')
  })

  it('context_generated with source_count returns "Context generated from {n} sources"', () => {
    const event = mockEvent({
      event_type: 'context_generated',
      metadata: { source_count: 5 },
    })
    expect(formatEventDescription(event)).toBe(
      'Context generated from 5 sources'
    )
  })

  it('integration_connected with integration metadata returns "{integration} connected"', () => {
    const event = mockEvent({
      event_type: 'integration_connected',
      metadata: { integration: 'GitHub' },
    })
    expect(formatEventDescription(event)).toBe('GitHub connected')
  })

  it('integration_disconnected with integration metadata returns "{integration} disconnected"', () => {
    const event = mockEvent({
      event_type: 'integration_disconnected',
      metadata: { integration: 'Notion' },
    })
    expect(formatEventDescription(event)).toBe('Notion disconnected')
  })

  it('unknown metadata falls back to "Unknown" for integration name', () => {
    const event = mockEvent({
      event_type: 'sync_started',
      metadata: {},
    })
    expect(formatEventDescription(event)).toBe('Unknown sync started')
  })
})

describe('formatEventDescription - messages_digest', () => {
  it('returns integration name with message and channel count', () => {
    const event = mockEvent({
      event_type: 'messages_digest',
      metadata: { integration: 'telegram', message_count: 127, channels_active: 5 },
    })
    expect(formatEventDescription(event)).toBe('telegram digest — 127 messages, 5 channels')
  })

  it('handles singular channel', () => {
    const event = mockEvent({
      event_type: 'messages_digest',
      metadata: { integration: 'slack', message_count: 12, channels_active: 1 },
    })
    expect(formatEventDescription(event)).toBe('slack digest — 12 messages, 1 channel')
  })
})

describe('getEventSubtitle', () => {
  it('ticket_created with ticket_id shows integration and id', () => {
    const event = mockEvent({
      event_type: 'ticket_created',
      metadata: { integration: 'linear', ticket_id: 'LIN-123', title: 'Bug' },
    })
    expect(getEventSubtitle(event)).toBe('linear LIN-123')
  })

  it('pr_merged with repo shows repo#number', () => {
    const event = mockEvent({
      event_type: 'pr_merged',
      metadata: { repo: 'org/repo', pr_number: 42, title: 'Fix' },
    })
    expect(getEventSubtitle(event)).toBe('org/repo#42')
  })

  it('sync_started returns null', () => {
    const event = mockEvent({ event_type: 'sync_started' })
    expect(getEventSubtitle(event)).toBeNull()
  })
})

describe('formatTimelineTimestamp', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-02-28T15:42:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('< 1 minute ago returns "just now"', () => {
    const date = new Date('2026-02-28T15:41:30Z').toISOString()
    expect(formatTimelineTimestamp(date)).toBe('just now')
  })

  it('5 minutes ago returns "5m ago"', () => {
    const date = new Date('2026-02-28T15:37:00Z').toISOString()
    expect(formatTimelineTimestamp(date)).toBe('5m ago')
  })

  it('3 hours ago returns "3h ago"', () => {
    const date = new Date('2026-02-28T12:42:00Z').toISOString()
    expect(formatTimelineTimestamp(date)).toBe('3h ago')
  })

  it('25 hours ago returns absolute time like "3:42 PM"', () => {
    const date = new Date('2026-02-27T14:42:00Z').toISOString()
    const result = formatTimelineTimestamp(date)
    // Should be absolute time format (not relative)
    expect(result).not.toContain('ago')
    expect(result).not.toBe('just now')
    // Should contain AM/PM
    expect(result).toMatch(/\d{1,2}:\d{2}\s?(AM|PM)/i)
  })
})

describe('formatFullTimestamp', () => {
  it('formats date as "Month Day, Year at H:MM AM/PM"', () => {
    const date = new Date('2026-02-28T15:42:00Z').toISOString()
    const result = formatFullTimestamp(date)
    // Should contain "Feb 28, 2026" and "at" and time
    expect(result).toContain('Feb')
    expect(result).toContain('28')
    expect(result).toContain('2026')
    expect(result).toContain('at')
    expect(result).toMatch(/\d{1,2}:\d{2}\s?(AM|PM)/i)
  })
})

describe('formatDayLabel', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-02-28T15:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('today returns "TODAY"', () => {
    expect(formatDayLabel('2026-02-28T10:00:00Z')).toBe('TODAY')
  })

  it('yesterday returns "YESTERDAY"', () => {
    expect(formatDayLabel('2026-02-27T10:00:00Z')).toBe('YESTERDAY')
  })

  it('3 days ago returns weekday name uppercase', () => {
    // Feb 25 is a Wednesday
    const result = formatDayLabel('2026-02-25T10:00:00Z')
    expect(result).toBe('WEDNESDAY')
  })

  it('10 days ago returns "FEB 18, 2026" format', () => {
    const result = formatDayLabel('2026-02-18T10:00:00Z')
    expect(result).toMatch(/FEB\s+18,\s+2026/i)
    expect(result).toBe(result.toUpperCase())
  })
})

describe('groupEventsByDay', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-02-28T15:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('groups events by date into buckets with label, date, and events', () => {
    const events: ActivityEvent[] = [
      mockEvent({
        id: 'e1',
        created_at: '2026-02-28T14:00:00Z',
        event_type: 'sync_started',
      }),
      mockEvent({
        id: 'e2',
        created_at: '2026-02-28T10:00:00Z',
        event_type: 'sync_completed',
      }),
      mockEvent({
        id: 'e3',
        created_at: '2026-02-27T08:00:00Z',
        event_type: 'context_generated',
      }),
    ]

    const groups = groupEventsByDay(events)

    expect(groups).toHaveLength(2)
    expect(groups[0].label).toBe('TODAY')
    expect(groups[0].events).toHaveLength(2)
    expect(groups[1].label).toBe('YESTERDAY')
    expect(groups[1].events).toHaveLength(1)
  })

  it('returns empty array for empty events', () => {
    expect(groupEventsByDay([])).toEqual([])
  })

  it('preserves chronological order within each group', () => {
    const events: ActivityEvent[] = [
      mockEvent({ id: 'e1', created_at: '2026-02-28T14:00:00Z' }),
      mockEvent({ id: 'e2', created_at: '2026-02-28T10:00:00Z' }),
    ]

    const groups = groupEventsByDay(events)
    expect(groups[0].events[0].id).toBe('e1')
    expect(groups[0].events[1].id).toBe('e2')
  })
})
