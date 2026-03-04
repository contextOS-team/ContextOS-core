'use client'

/**
 * Realtime subscription hook for the context_pages table.
 *
 * Listens for INSERT and UPDATE events via Supabase postgres_changes.
 * Uses refs for callbacks to avoid stale closures and prevent
 * re-subscriptions when callbacks change.
 *
 * CRITICAL: Calls supabase.removeChannel(channel) on cleanup to prevent
 * "TooManyChannels" errors under React Strict Mode (double-invoke).
 */

import { useEffect, useRef } from 'react'
import { createClient } from '@/lib/supabase/client'
import type { RealtimePostgresChangesPayload } from '@supabase/supabase-js'

type RowPayload = RealtimePostgresChangesPayload<Record<string, unknown>>

interface UseContextPagesRealtimeOptions {
  onInsert?: (payload: RowPayload) => void
  onUpdate?: (payload: RowPayload) => void
}

export function useContextPagesRealtime({
  onInsert,
  onUpdate,
}: UseContextPagesRealtimeOptions = {}) {
  const onInsertRef = useRef(onInsert)
  const onUpdateRef = useRef(onUpdate)

  // Keep refs in sync with latest callbacks
  onInsertRef.current = onInsert
  onUpdateRef.current = onUpdate

  useEffect(() => {
    const supabase = createClient()

    const channel = supabase
      .channel('context-pages-changes')
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'context_pages',
        },
        (payload: RowPayload) => {
          if (payload.eventType === 'INSERT') {
            onInsertRef.current?.(payload)
          } else if (payload.eventType === 'UPDATE') {
            onUpdateRef.current?.(payload)
          }
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
}
