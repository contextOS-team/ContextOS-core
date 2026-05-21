'use client'

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase/client'

export type SyncState =
  | { kind: 'unknown' }
  | { kind: 'idle'; lastUpdatedAt: Date }
  | { kind: 'syncing'; provider: string; progress: number | null }
  | { kind: 'error'; provider: string; message: string }

type SyncEventRow = {
  event_type: string
  created_at: string
  metadata: Record<string, unknown> | null
}

const SOURCE_ACTIVITY_EVENT_TYPES = [
  'context_generated',
  'messages_digest',
  'ticket_created',
  'pr_merged',
  'meeting_recorded',
  'page_created',
] as const
const SYNC_EVENT_TYPES = ['sync_completed', 'sync_started'] as const
const CHROME_STATUS_EVENT_TYPES = [...SYNC_EVENT_TYPES, ...SOURCE_ACTIVITY_EVENT_TYPES] as const
const INITIAL_SYNC_EVENT_LIMIT = 12
const ACTIVE_SYNC_STARTED_WINDOW_MS = 15 * 60_000

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
      lastUpdatedAt: new Date(row.created_at),
    }
  }

  if ((SOURCE_ACTIVITY_EVENT_TYPES as readonly string[]).includes(row.event_type)) {
    return {
      kind: 'idle',
      lastUpdatedAt: new Date(row.created_at),
    }
  }

  return null
}

function isFreshStartedRow(row: SyncEventRow, nowMs: number): boolean {
  const createdAtMs = new Date(row.created_at).getTime()
  return Number.isFinite(createdAtMs) && nowMs - createdAtMs <= ACTIVE_SYNC_STARTED_WINDOW_MS
}

function initialStateFromSyncRows(rows: SyncEventRow[], nowMs = Date.now()): SyncState | null {
  for (const row of rows) {
    if (row.event_type === 'sync_started' && !isFreshStartedRow(row, nowMs)) {
      continue
    }

    const next = stateFromSyncRow(row)
    if (next) return next
  }

  return null
}

/**
 * Dashboard chrome status state.
 *
 * CONTEXT.md §8 defines the three-state chrome cluster. The idle timestamp uses
 * recent source activity, not only `sync_completed`, because Slack digests and
 * webhook events can bring in fresh workspace data without a full sync lifecycle
 * row. Error detection stays intentionally derived from `metadata.error` on
 * `sync_completed` rows because migrations 00031 and 00033 define the complete
 * activity_events event set. Initial load ignores stale `sync_started` rows so
 * old interrupted syncs do not make the chrome claim it is actively syncing
 * forever; fresh Realtime starts still move the cluster into syncing
 * immediately. The cleanup closes over the local channel variable for
 * StrictMode safety.
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
        .in('event_type', [...CHROME_STATUS_EVENT_TYPES])
        .order('created_at', { ascending: false })
        .limit(INITIAL_SYNC_EVENT_LIMIT)

      if (cancelled || !data) return

      const rows = Array.isArray(data) ? (data as SyncEventRow[]) : []
      const next = initialStateFromSyncRows(rows)
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
