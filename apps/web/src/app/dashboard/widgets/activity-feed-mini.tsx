'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { createClient } from '@/lib/supabase/client'
import { Skeleton } from '@/components/ui/skeleton'
import { Zap } from 'lucide-react'
import { type ActivityEvent, EVENT_ICONS } from '../activity/types'
import { formatEventDescription, formatTimelineTimestamp } from '../activity/formatters'

interface ActivityFeedMiniProps {
  workspaceId: string | null
}

export function ActivityFeedMini({ workspaceId }: ActivityFeedMiniProps) {
  const [events, setEvents] = useState<ActivityEvent[] | null>(null)

  useEffect(() => {
    if (!workspaceId) return
    let cancelled = false

    createClient()
      .from('activity_events')
      .select('*')
      .eq('workspace_id', workspaceId)
      .order('created_at', { ascending: false })
      .limit(5)
      .then(
        ({ data }) => { if (!cancelled) setEvents((data as ActivityEvent[]) ?? []) },
        () => { if (!cancelled) setEvents([]) },
      )

    return () => { cancelled = true }
  }, [workspaceId])

  if (events === null) {
    return (
      <div>
        <Skeleton className="h-3 w-28 mb-3" />
        <div className="widget-card rounded-xl divide-y divide-border">
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
      <div className="widget-card rounded-xl divide-y divide-border">
        {events.map((event) => {
          const Icon = EVENT_ICONS[event.event_type] ?? Zap
          return (
            <div key={event.id} className="px-4 py-2.5 flex items-center gap-3 transition-colors duration-150 hover:bg-muted/40">
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
