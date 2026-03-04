import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { ActivityEvent } from '../types'
import {
  formatEventDescription,
  formatTimelineTimestamp,
  formatFullTimestamp,
  formatDayLabel,
  getMetadataChip,
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

  it('user_signed_up returns "Workspace created"', () => {
    const event = mockEvent({ event_type: 'user_signed_up' })
    expect(formatEventDescription(event)).toBe('Workspace created')
  })

  it('unknown metadata falls back to "Unknown" for integration name', () => {
    const event = mockEvent({
      event_type: 'sync_started',
      metadata: {},
    })
    expect(formatEventDescription(event)).toBe('Unknown sync started')
  })
})

describe('getMetadataChip', () => {
  it('sync_completed with items_count returns "{n} items"', () => {
    const event = mockEvent({
      event_type: 'sync_completed',
      metadata: { items_count: 42 },
    })
    expect(getMetadataChip(event)).toBe('42 items')
  })

  it('sync_completed with duration_ms returns formatted seconds', () => {
    const event = mockEvent({
      event_type: 'sync_completed',
      metadata: { duration_ms: 1200 },
    })
    expect(getMetadataChip(event)).toBe('1.2s')
  })

  it('sync_completed with both items_count and duration_ms prioritizes items_count', () => {
    const event = mockEvent({
      event_type: 'sync_completed',
      metadata: { items_count: 42, duration_ms: 1200 },
    })
    expect(getMetadataChip(event)).toBe('42 items')
  })

  it('context_generated with token_count >= 1000 returns "k tokens" format', () => {
    const event = mockEvent({
      event_type: 'context_generated',
      metadata: { token_count: 3200 },
    })
    expect(getMetadataChip(event)).toBe('3.2k tokens')
  })

  it('context_generated with token_count < 1000 returns "{n} tokens"', () => {
    const event = mockEvent({
      event_type: 'context_generated',
      metadata: { token_count: 500 },
    })
    expect(getMetadataChip(event)).toBe('500 tokens')
  })

  it('sync_started returns null (no chip)', () => {
    const event = mockEvent({ event_type: 'sync_started' })
    expect(getMetadataChip(event)).toBeNull()
  })

  it('user_signed_up returns null (no chip)', () => {
    const event = mockEvent({ event_type: 'user_signed_up' })
    expect(getMetadataChip(event)).toBeNull()
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
