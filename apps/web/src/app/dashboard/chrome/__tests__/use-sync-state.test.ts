// @vitest-environment jsdom

import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
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

function makeSupabaseMock(initialRow: SyncRow | null = null) {
  let realtimeCallback: ((payload: { new: SyncRow }) => void) | null = null
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
    limit: vi.fn(() => query),
    maybeSingle: vi.fn(async () => ({ data: initialRow, error: null })),
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
      lastSyncedAt: new Date('2026-05-20T12:00:00Z'),
    })
    expect(supabase.from).toHaveBeenCalledWith('activity_events')
    expect(supabase.query.in).toHaveBeenCalledWith('event_type', ['sync_completed', 'sync_started'])
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
      lastSyncedAt: new Date('2026-05-20T12:01:00Z'),
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
