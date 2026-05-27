import { beforeEach, describe, expect, it, vi } from 'vitest'
import { bucketDelta, fetchActivityDelta } from '../activity-delta'
import type { NeedsYouItem } from '../../types'

const createClientMock = vi.fn()

vi.mock('@/lib/supabase/client', () => ({
  createClient: () => createClientMock(),
}))

function row(id: string, event_type: string, created_at = '2026-05-20T12:00:00Z') {
  return { id, event_type, created_at }
}

function needsYou(overrides: Partial<NeedsYouItem> = {}): NeedsYouItem {
  return {
    id: overrides.id ?? 'needs-1',
    ticketId: overrides.ticketId ?? 'RD-786',
    person: overrides.person ?? 'Vasiliy',
    sinceDay: overrides.sinceDay ?? 'Tuesday',
    assignedToCurrentUser: overrides.assignedToCurrentUser ?? true,
    ageMs: overrides.ageMs ?? 4 * 24 * 60 * 60 * 1000,
  }
}

describe('bucketDelta', () => {
  it('returns zeroed buckets for empty input', () => {
    expect(bucketDelta([], [], 'user-1')).toEqual({
      decisions: { count: 0, items: [] },
      sources: { count: 0, items: [] },
      needsYou: { topUrgentItem: null, items: [] },
    })
  })

  it('counts decision and source rows by locked activity event types', () => {
    const result = bucketDelta(
      [
        row('decision-1', 'context_generated'),
        row('decision-2', 'messages_digest'),
        row('source-1', 'ticket_created'),
        row('source-2', 'pr_merged'),
        row('source-3', 'meeting_recorded'),
        row('source-4', 'page_created'),
        row('source-5', 'integration_connected'),
        row('source-6', 'sync_completed'),
      ],
      [],
      'user-1'
    )

    expect(result.decisions.count).toBe(2)
    expect(result.decisions.items.map((item) => item.id)).toEqual(['decision-1', 'decision-2'])
    expect(result.sources.count).toBe(6)
    expect(result.sources.items.map((item) => item.id)).toEqual([
      'source-1',
      'source-2',
      'source-3',
      'source-4',
      'source-5',
      'source-6',
    ])
  })

  it('ignores unknown or incomplete event types', () => {
    const result = bucketDelta(
      [
        row('ignored-1', 'sync_started'),
        row('ignored-2', 'integration_disconnected'),
      ],
      [],
      'user-1'
    )

    expect(result.decisions.count).toBe(0)
    expect(result.sources.count).toBe(0)
  })

  it('keeps an assigned needs-you item dominant even with large buckets', () => {
    const rows = Array.from({ length: 30 }, (_, index) => row(`decision-${index}`, 'context_generated'))
    const result = bucketDelta(
      rows,
      [
        needsYou({ id: 'newer', ageMs: 1_000 }),
        needsYou({ id: 'oldest', ageMs: 10_000, ticketId: 'RD-999' }),
      ],
      'user-1'
    )

    expect(result.decisions.count).toBe(30)
    expect(result.needsYou.topUrgentItem).toEqual({
      person: 'Vasiliy',
      ticketId: 'RD-999',
      sinceDay: 'Tuesday',
    })
  })

  it('returns no top urgent item when nothing is assigned to the current user', () => {
    const result = bucketDelta(
      [row('decision-1', 'context_generated')],
      [needsYou({ assignedToCurrentUser: false })],
      'user-1'
    )

    expect(result.needsYou.topUrgentItem).toBeNull()
  })
})

describe('fetchActivityDelta', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  function mockQuery() {
    const query = {
      from: vi.fn(),
      select: vi.fn(),
      eq: vi.fn(),
      gt: vi.fn(),
      order: vi.fn(),
      limit: vi.fn(),
      then: vi.fn((resolve: (value: { data: unknown[]; error: null }) => void) => {
        resolve({ data: [], error: null })
      }),
    }

    query.from.mockReturnValue(query)
    query.select.mockReturnValue(query)
    query.eq.mockReturnValue(query)
    query.gt.mockReturnValue(query)
    query.order.mockReturnValue(query)
    query.limit.mockReturnValue(query)
    createClientMock.mockReturnValue(query)

    return query
  }

  it('does not add a created_at filter when since is null', async () => {
    const query = mockQuery()

    await fetchActivityDelta('workspace-1', null)

    expect(query.from).toHaveBeenCalledWith('activity_events')
    expect(query.eq).toHaveBeenCalledWith('workspace_id', 'workspace-1')
    expect(query.gt).not.toHaveBeenCalled()
    expect(query.order).toHaveBeenCalledWith('created_at', { ascending: false })
    expect(query.limit).toHaveBeenCalledWith(200)
  })

  it('adds a created_at gt filter when since is provided', async () => {
    const query = mockQuery()
    const since = new Date('2026-05-20T10:00:00Z')

    await fetchActivityDelta('workspace-1', since)

    expect(query.gt).toHaveBeenCalledWith('created_at', since.toISOString())
  })
})
