'use client'

import { useEffect, useRef, useState } from 'react'
import { createClient } from '@/lib/supabase/client'

const INACTIVITY_HYSTERESIS_MS = 5 * 60 * 1000
const INACTIVITY_CHECK_MS = 30 * 1000

/**
 * Reads the dashboard last-visited timestamp once and keeps that value stable
 * for the full session. Per CONTEXT.md §9 and RESEARCH Pitfall 5, the
 * inactivity write advances server state only; it intentionally does not call
 * setState, so visible markers do not decay mid-visit.
 */
export function useLastVisitedAt(workspaceId: string | null): Date | null {
  const [lastVisitedAt, setLastVisitedAt] = useState<Date | null>(null)
  const supabaseRef = useRef(createClient())
  const userIdRef = useRef<string | null>(null)
  const lastActivityRef = useRef(Date.now())

  useEffect(() => {
    let cancelled = false
    const supabase = supabaseRef.current

    async function loadLastVisitedAt() {
      const {
        data: { user },
      } = await supabase.auth.getUser()

      if (cancelled) return

      userIdRef.current = user?.id ?? null

      if (!user || !workspaceId) {
        setLastVisitedAt(null)
        return
      }

      const { data } = await supabase
        .from('dashboard_user_state')
        .select('last_visited_at')
        .eq('user_id', user.id)
        .eq('workspace_id', workspaceId)
        .maybeSingle()

      if (cancelled) return

      setLastVisitedAt(data?.last_visited_at ? new Date(data.last_visited_at) : null)
    }

    loadLastVisitedAt()

    return () => {
      cancelled = true
    }
  }, [workspaceId])

  useEffect(() => {
    if (!workspaceId) return

    const supabase = supabaseRef.current
    const updateActivity = () => {
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return
      lastActivityRef.current = Date.now()
    }

    const writeAfterInactivity = async () => {
      const userId = userIdRef.current
      if (!userId) return

      const inactiveFor = Date.now() - lastActivityRef.current
      if (inactiveFor < INACTIVITY_HYSTERESIS_MS) return

      await supabase.from('dashboard_user_state').upsert(
        {
          user_id: userId,
          workspace_id: workspaceId,
          last_visited_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
        { onConflict: 'user_id,workspace_id' }
      )

      lastActivityRef.current = Date.now()
    }

    window.addEventListener('pointermove', updateActivity, { passive: true })
    window.addEventListener('keydown', updateActivity)
    window.addEventListener('scroll', updateActivity, { passive: true })
    document.addEventListener('visibilitychange', updateActivity)

    const interval = window.setInterval(() => {
      void writeAfterInactivity()
    }, INACTIVITY_CHECK_MS)

    return () => {
      window.removeEventListener('pointermove', updateActivity)
      window.removeEventListener('keydown', updateActivity)
      window.removeEventListener('scroll', updateActivity)
      document.removeEventListener('visibilitychange', updateActivity)
      window.clearInterval(interval)
    }
  }, [workspaceId])

  return lastVisitedAt
}
