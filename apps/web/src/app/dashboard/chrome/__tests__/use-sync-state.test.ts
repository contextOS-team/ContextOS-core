// @vitest-environment jsdom

import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useSyncState } from '../use-sync-state'

const createClientMock = vi.fn()

vi.mock('@/lib/supabase/client', () => ({
  createClient: () => createClientMock(),
}))

type SyncRow = {
  event_type: string
  created_at: string
  metadata?: Record<string, unknown> | null
}

function makeSupabaseMock(initialRows: SyncRow | SyncRow[] | null = null) {
  let realtimeCallback: ((payload: { new: SyncRow }) => void) | null = null
  const rows = Array.isArray(initialRows)
    ? initialRows
    : initialRows
      ? [initialRows]
      : []
  const channel = {
    on: vi.fn((_event, _filter, callback) => {
      realtimeCallback = callback
      return channel
    }),
    subscribe: vi.fn(() => channel),
  }

  const query = {
    select: vi.fn(() => query),
    eq: vi.fn(() => query),
    in: vi.fn(() => query),
    order: vi.fn(() => query),
    limit: vi.fn(async () => ({ data: rows, error: null })),
  }

  const supabase = {
    from: vi.fn(() => query),
    channel: vi.fn(() => channel),
    removeChannel: vi.fn(),
    emit: (row: SyncRow) => {
      realtimeCallback?.({ new: row })
    },
    channelRef: channel,
    query,
  }

  return supabase
}

describe('useSyncState', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns unknown and never subscribes without a workspace id', () => {
    const supabase = makeSupabaseMock()
    createClientMock.mockReturnValue(supabase)

    const { result } = renderHook(() => useSyncState(null))

    expect(result.current).toEqual({ kind: 'unknown' })
    expect(createClientMock).not.toHaveBeenCalled()
    expect(supabase.channel).not.toHaveBeenCalled()
  })

  it('loads the most recent sync event and transitions to idle', async () => {
    const row = {
      event_type: 'sync_completed',
      created_at: '2026-05-20T12:00:00Z',
      metadata: { integration: 'slack' },
    }
    const supabase = makeSupabaseMock(row)
    createClientMock.mockReturnValue(supabase)

    const { result } = renderHook(() => useSyncState('workspace-1'))

    await waitFor(() => expect(result.current.kind).toBe('idle'))
    expect(result.current).toEqual({
      kind: 'idle',
      lastUpdatedAt: new Date('2026-05-20T12:00:00Z'),
    })
    expect(supabase.from).toHaveBeenCalledWith('activity_events')
    expect(supabase.query.in).toHaveBeenCalledWith('event_type', [
      'sync_completed',
      'sync_started',
      'context_generated',
      'messages_digest',
      'ticket_created',
      'pr_merged',
      'meeting_recorded',
      'page_created',
    ])
    expect(supabase.query.limit).toHaveBeenCalledWith(12)
  })

  it('uses newer source activity instead of an older sync lifecycle row for idle recency', async () => {
    const supabase = makeSupabaseMock([
      {
        event_type: 'messages_digest',
        created_at: '2026-05-20T12:00:00Z',
        metadata: { integration: 'slack' },
      },
      {
        event_type: 'sync_completed',
        created_at: '2026-05-17T12:00:00Z',
        metadata: { integration: 'jira' },
      },
    ])
    createClientMock.mockReturnValue(supabase)

    const { result } = renderHook(() => useSyncState('workspace-1'))

    await waitFor(() => expect(result.current.kind).toBe('idle'))
    expect(result.current).toEqual({
      kind: 'idle',
      lastUpdatedAt: new Date('2026-05-20T12:00:00Z'),
    })
  })

  it('loads a fresh sync_started event as syncing on initial load', async () => {
    const nowSpy = vi.spyOn(Date, 'now').mockReturnValue(new Date('2026-05-20T12:04:00Z').getTime())

    const supabase = makeSupabaseMock({
      event_type: 'sync_started',
      created_at: '2026-05-20T12:00:00Z',
      metadata: { integration: 'jira', progress: 0.2 },
    })
    createClientMock.mockReturnValue(supabase)

    const { result } = renderHook(() => useSyncState('workspace-1'))

    await waitFor(() => expect(result.current.kind).toBe('syncing'))
    expect(result.current).toEqual({ kind: 'syncing', provider: 'jira', progress: 0.2 })
    nowSpy.mockRestore()
  })

  it('falls back to the latest completed sync when the newest started row is stale', async () => {
    const nowSpy = vi.spyOn(Date, 'now').mockReturnValue(new Date('2026-05-20T12:30:00Z').getTime())

    const supabase = makeSupabaseMock([
      {
        event_type: 'sync_started',
        created_at: '2026-05-20T12:00:00Z',
        metadata: { integration: 'jira' },
      },
      {
        event_type: 'sync_completed',
        created_at: '2026-05-20T11:58:00Z',
        metadata: { integration: 'jira' },
      },
    ])
    createClientMock.mockReturnValue(supabase)

    const { result } = renderHook(() => useSyncState('workspace-1'))

    await waitFor(() => expect(result.current.kind).toBe('idle'))
    expect(result.current).toEqual({
      kind: 'idle',
      lastUpdatedAt: new Date('2026-05-20T11:58:00Z'),
    })
    nowSpy.mockRestore()
  })

  it('transitions to syncing on sync_started realtime payloads', async () => {
    const supabase = makeSupabaseMock()
    createClientMock.mockReturnValue(supabase)

    const { result } = renderHook(() => useSyncState('workspace-1'))
    await waitFor(() => expect(supabase.channel).toHaveBeenCalled())

    act(() => {
      supabase.emit({
        event_type: 'sync_started',
        created_at: '2026-05-20T12:00:00Z',
        metadata: { integration: 'slack' },
      })
    })

    expect(result.current).toEqual({ kind: 'syncing', provider: 'slack', progress: null })
  })

  it('transitions from syncing to idle on sync_completed without metadata.error', async () => {
    const supabase = makeSupabaseMock()
    createClientMock.mockReturnValue(supabase)

    const { result } = renderHook(() => useSyncState('workspace-1'))
    await waitFor(() => expect(supabase.channel).toHaveBeenCalled())

    act(() => {
      supabase.emit({
        event_type: 'sync_started',
        created_at: '2026-05-20T12:00:00Z',
        metadata: { integration: 'slack', progress: 0.35 },
      })
      supabase.emit({
        event_type: 'sync_completed',
        created_at: '2026-05-20T12:01:00Z',
        metadata: { integration: 'slack' },
      })
    })

    expect(result.current).toEqual({
      kind: 'idle',
      lastUpdatedAt: new Date('2026-05-20T12:01:00Z'),
    })
  })

  it('transitions to idle recency on source activity realtime payloads', async () => {
    const supabase = makeSupabaseMock()
    createClientMock.mockReturnValue(supabase)

    const { result } = renderHook(() => useSyncState('workspace-1'))
    await waitFor(() => expect(supabase.channel).toHaveBeenCalled())

    act(() => {
      supabase.emit({
        event_type: 'messages_digest',
        created_at: '2026-05-20T12:05:00Z',
        metadata: { integration: 'slack' },
      })
    })

    expect(result.current).toEqual({
      kind: 'idle',
      lastUpdatedAt: new Date('2026-05-20T12:05:00Z'),
    })
  })

  it('uses metadata.error on sync_completed as the single error signal', async () => {
    const supabase = makeSupabaseMock()
    createClientMock.mockReturnValue(supabase)

    const { result } = renderHook(() => useSyncState('workspace-1'))
    await waitFor(() => expect(supabase.channel).toHaveBeenCalled())

    act(() => {
      supabase.emit({
        event_type: 'sync_completed',
        created_at: '2026-05-20T12:01:00Z',
        metadata: { integration: 'slack', error: 'OAuth token expired' },
      })
    })

    expect(result.current).toEqual({
      kind: 'error',
      provider: 'slack',
      message: 'OAuth token expired',
    })
  })

  it('removes the realtime channel on unmount', async () => {
    const supabase = makeSupabaseMock()
    createClientMock.mockReturnValue(supabase)

    const { unmount } = renderHook(() => useSyncState('workspace-1'))
    await waitFor(() => expect(supabase.channel).toHaveBeenCalled())

    unmount()

    expect(supabase.removeChannel).toHaveBeenCalledTimes(1)
    expect(supabase.removeChannel).toHaveBeenCalledWith(supabase.channelRef)
  })
})
