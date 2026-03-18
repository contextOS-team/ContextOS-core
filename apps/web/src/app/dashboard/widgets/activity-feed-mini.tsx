'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { createClient } from '@/lib/supabase/client'
import { Skeleton } from '@/components/ui/skeleton'
import { Zap } from 'lucide-react'
import { type ActivityEvent, EVENT_ICONS } from '../activity/types'
import { formatEventDescription, formatTimelineTimestamp } from '../activity/formatters'

export function ActivityFeedMini() {
  const [events, setEvents] = useState<ActivityEvent[] | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      const supabase = createClient()
      const {
        data: { user },
      } = await supabase.auth.getUser()
      if (!user || cancelled) return

      const { data: membership } = await supabase
        .from('workspace_members')
        .select('workspace_id')
        .eq('user_id', user.id)
        .single()
      if (!membership || cancelled) return

      const { data } = await supabase
        .from('activity_events')
        .select('*')
        .eq('workspace_id', membership.workspace_id)
        .order('created_at', { ascending: false })
        .limit(5)

      if (!cancelled) {
        setEvents((data as ActivityEvent[]) ?? [])
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [])

  // Loading state
  if (events === null) {
    return (
      <div>
        <Skeleton className="h-3 w-28 mb-3" />
        <div className="rounded-xl bg-card shadow-[0_0_0_1px_rgba(255,255,255,0.04),0_1px_2px_rgba(0,0,0,0.2),0_2px_8px_rgba(0,0,0,0.12)] overflow-hidden divide-y divide-border">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="px-4 py-2.5 flex items-center gap-3">
              <Skeleton className="h-4 w-4 shrink-0 rounded" />
              <Skeleton className="h-3.5 w-48 flex-1" />
              <Skeleton className="h-3 w-12 shrink-0" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  // No events — render nothing
  if (events.length === 0) return null

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="section-label">Recent Activity</h3>
        <Link
          href="/dashboard/activity"
          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          View all
        </Link>
      </div>
      <div className="rounded-xl bg-card shadow-[0_0_0_1px_rgba(255,255,255,0.04),0_1px_2px_rgba(0,0,0,0.2),0_2px_8px_rgba(0,0,0,0.12)] overflow-hidden divide-y divide-border">
        {events.map((event) => {
          const Icon = EVENT_ICONS[event.event_type] ?? Zap
          return (
            <div key={event.id} className="px-4 py-2.5 flex items-center gap-3">
              <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="text-sm text-foreground truncate">
                {formatEventDescription(event)}
              </span>
              <span className="text-xs text-muted-foreground shrink-0 font-mono tabular-nums ml-auto">
                {formatTimelineTimestamp(event.created_at)}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
