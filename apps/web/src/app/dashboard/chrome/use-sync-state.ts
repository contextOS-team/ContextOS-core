'use client'

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase/client'

export type SyncState =
  | { kind: 'unknown' }
  | { kind: 'idle'; lastSyncedAt: Date }
  | { kind: 'syncing'; provider: string; progress: number | null }
  | { kind: 'error'; provider: string; message: string }

type SyncEventRow = {
  event_type: string
  created_at: string
  metadata: Record<string, unknown> | null
}

const SYNC_EVENT_TYPES = ['sync_completed', 'sync_started'] as const

function metadataString(metadata: Record<string, unknown> | null, key: string): string | null {
  const value = metadata?.[key]
  return typeof value === 'string' && value.length > 0 ? value : null
}

function metadataProgress(metadata: Record<string, unknown> | null): number | null {
  const value = metadata?.progress
  return typeof value === 'number' ? value : null
}

function stateFromSyncRow(row: SyncEventRow): SyncState | null {
  const provider = metadataString(row.metadata, 'integration') ?? 'unknown'

  if (row.event_type === 'sync_started') {
    return {
      kind: 'syncing',
      provider,
      progress: metadataProgress(row.metadata),
    }
  }

  if (row.event_type === 'sync_completed') {
    const error = metadataString(row.metadata, 'error')

    if (error) {
      return {
        kind: 'error',
        provider,
        message: error,
      }
    }

    return {
      kind: 'idle',
      lastSyncedAt: new Date(row.created_at),
    }
  }

  return null
}

/**
 * Dashboard chrome sync state.
 *
 * CONTEXT.md §8 defines the three-state chrome cluster. Error detection is
 * intentionally derived from `metadata.error` on `sync_completed` rows because
 * migrations 00031 and 00033 define the complete activity_events event set.
 * The cleanup closes over the local channel variable for StrictMode safety.
 */
export function useSyncState(workspaceId: string | null): SyncState {
  const [state, setState] = useState<SyncState>({ kind: 'unknown' })

  useEffect(() => {
    if (!workspaceId) {
      setState({ kind: 'unknown' })
      return
    }

    let cancelled = false
    const supabase = createClient()

    async function loadInitialState() {
      const { data } = await supabase
        .from('activity_events')
        .select('event_type, created_at, metadata')
        .eq('workspace_id', workspaceId)
        .in('event_type', [...SYNC_EVENT_TYPES])
        .order('created_at', { ascending: false })
        .limit(1)
        .maybeSingle()

      if (cancelled || !data) return

      const next = stateFromSyncRow(data as SyncEventRow)
      if (next) setState(next)
    }

    void loadInitialState()

    const channel = supabase
      .channel(`dashboard-sync-${workspaceId}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'activity_events',
          filter: `workspace_id=eq.${workspaceId}`,
        },
        (payload) => {
          const next = stateFromSyncRow(payload.new as SyncEventRow)
          if (!next) return
          setState(() => next)
        }
      )
      .subscribe()

    return () => {
      cancelled = true
      supabase.removeChannel(channel)
    }
  }, [workspaceId])

  return state
}
