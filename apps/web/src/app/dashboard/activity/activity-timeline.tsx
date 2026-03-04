'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Clock, ArrowUp } from 'lucide-react'
import Link from 'next/link'
import { createClient } from '@/lib/supabase/client'
import { Skeleton } from '@/components/ui/skeleton'
import type { ActivityEvent, EventType } from './types'
import { EVENT_ICONS } from './types'
import {
  formatEventDescription,
  getMetadataChip,
  formatTimelineTimestamp,
  formatFullTimestamp,
  groupEventsByDay,
} from './formatters'

const PAGE_SIZE = 30

interface ActivityTimelineProps {
  initialEvents: ActivityEvent[]
  workspaceId: string
}

export function ActivityTimeline({
  initialEvents,
  workspaceId,
}: ActivityTimelineProps) {
  const [events, setEvents] = useState<ActivityEvent[]>(initialEvents)
  const [bufferedEvents, setBufferedEvents] = useState<ActivityEvent[]>([])
  const [hasMore, setHasMore] = useState(initialEvents.length === PAGE_SIZE)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [, setTick] = useState(0)

  const newEventIds = useRef(new Set<string>())
  const paginationSentinelRef = useRef<HTMLDivElement>(null)
  const timelineRef = useRef<HTMLDivElement>(null)
  const supabaseRef = useRef(createClient())

  // Scroll check stored in ref to avoid stale closure in Realtime callback
  const isScrolledToTopRef = useRef(true)

  // Track scroll position on main element
  useEffect(() => {
    const main = document.querySelector('main')
    if (!main) return

    function handleScroll() {
      isScrolledToTopRef.current = (main as HTMLElement).scrollTop === 0
      // Auto-flush buffer when user scrolls back to top
      if (isScrolledToTopRef.current) {
        setBufferedEvents((buf) => {
          if (buf.length === 0) return buf
          setEvents((prev) => [...buf, ...prev])
          return []
        })
      }
    }

    main.addEventListener('scroll', handleScroll, { passive: true })
    return () => main.removeEventListener('scroll', handleScroll)
  }, [])

  // Supabase Realtime subscription
  useEffect(() => {
    const supabase = supabaseRef.current
    const channel = supabase
      .channel(`activity-${workspaceId}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'activity_events',
          filter: `workspace_id=eq.${workspaceId}`,
        },
        (payload) => {
          const newEvent = payload.new as ActivityEvent
          newEventIds.current.add(newEvent.id)
          setTimeout(() => {
            newEventIds.current.delete(newEvent.id)
          }, 350)

          if (isScrolledToTopRef.current) {
            setEvents((prev) => [newEvent, ...prev])
          } else {
            setBufferedEvents((prev) => [newEvent, ...prev])
          }
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [workspaceId])

  // Timestamp refresh every 60s
  useEffect(() => {
    const interval = setInterval(() => setTick((t) => t + 1), 60_000)
    return () => clearInterval(interval)
  }, [])

  // IntersectionObserver for sticky day headers
  useEffect(() => {
    const container = timelineRef.current
    if (!container) return

    const sentinels = container.querySelectorAll<HTMLElement>('.day-sentinel')
    if (sentinels.length === 0) return

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const header = entry.target.nextElementSibling as HTMLElement | null
          if (!header) continue
          if (!entry.isIntersecting) {
            header.classList.add('border-b', 'border-border')
          } else {
            header.classList.remove('border-b', 'border-border')
          }
        }
      },
      { threshold: 0 }
    )

    sentinels.forEach((s) => observer.observe(s))
    return () => observer.disconnect()
  }, [events.length])

  // Cursor-based pagination via IntersectionObserver
  useEffect(() => {
    const sentinel = paginationSentinelRef.current
    if (!sentinel) return

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting && hasMore && !isLoadingMore) {
          loadMore()
        }
      },
      { rootMargin: '200px' }
    )

    observer.observe(sentinel)
    return () => observer.disconnect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasMore, isLoadingMore, events.length])

  const loadMore = useCallback(async () => {
    if (!hasMore || isLoadingMore) return
    setIsLoadingMore(true)

    const oldest = events[events.length - 1]
    if (!oldest) {
      setIsLoadingMore(false)
      return
    }

    const { data, error } = await supabaseRef.current
      .from('activity_events')
      .select('*')
      .eq('workspace_id', workspaceId)
      .lt('created_at', oldest.created_at)
      .order('created_at', { ascending: false })
      .limit(PAGE_SIZE)

    if (!error && data) {
      const typed = data as ActivityEvent[]
      setEvents((prev) => [...prev, ...typed])
      if (typed.length < PAGE_SIZE) setHasMore(false)
    }

    setIsLoadingMore(false)
  }, [hasMore, isLoadingMore, events, workspaceId])

  // Flush buffered events and scroll to top
  const flushBuffer = useCallback(() => {
    const main = document.querySelector('main')
    if (main) {
      main.scrollTo({ top: 0, behavior: 'smooth' })
    }
    setEvents((prev) => [...bufferedEvents, ...prev])
    setBufferedEvents([])
  }, [bufferedEvents])

  // Empty state
  if (events.length === 0 && bufferedEvents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <Clock className="h-8 w-8 text-muted-foreground mb-4" />
        <h2 className="text-lg font-medium text-foreground">Activity</h2>
        <p className="text-sm text-muted-foreground max-w-[320px] mx-auto mt-1">
          Events will appear here as you connect integrations and sync your
          data.
        </p>
        <Link
          href="/dashboard/integrations"
          className="text-sm text-muted-foreground underline-offset-4 hover:underline mt-3"
        >
          Connect an integration
        </Link>
      </div>
    )
  }

  const dayGroups = groupEventsByDay(events)

  return (
    <div ref={timelineRef} className="relative">
      {/* New events banner */}
      {bufferedEvents.length > 0 && (
        <div className="sticky top-0 z-20 flex justify-center py-2">
          <button
            onClick={flushBuffer}
            className="inline-flex items-center gap-1.5 bg-muted/80 backdrop-blur-sm text-sm text-foreground rounded-full px-3 py-1.5 animate-banner-slide-in cursor-pointer hover:bg-muted transition-colors duration-150"
          >
            <ArrowUp className="h-3.5 w-3.5" />
            {bufferedEvents.length} new event
            {bufferedEvents.length !== 1 ? 's' : ''}
          </button>
        </div>
      )}

      {/* Day groups */}
      {dayGroups.map((group) => (
        <div key={group.date}>
          {/* Sentinel for sticky header detection */}
          <div className="day-sentinel h-0" />
          <div className="section-label sticky top-0 z-10 bg-background pt-6 pb-3 transition-[border] duration-150">
            {group.label}
          </div>
          <div className="space-y-2">
            {group.events.map((event) => (
              <EventRow
                key={event.id}
                event={event}
                isNew={newEventIds.current.has(event.id)}
              />
            ))}
          </div>
        </div>
      ))}

      {/* Pagination sentinel */}
      <div ref={paginationSentinelRef} className="h-0" />

      {/* Loading more indicator */}
      {isLoadingMore && (
        <div className="space-y-2 pt-2">
          <div className="flex items-center gap-3 h-10">
            <Skeleton className="h-4 w-4 rounded shrink-0" />
            <Skeleton className="h-3.5 flex-1 max-w-[260px]" />
            <Skeleton className="h-3 w-14 ml-auto" />
          </div>
          <div className="flex items-center gap-3 h-10">
            <Skeleton className="h-4 w-4 rounded shrink-0" />
            <Skeleton className="h-3.5 flex-1 max-w-[200px]" />
            <Skeleton className="h-3 w-14 ml-auto" />
          </div>
        </div>
      )}

      {/* End of list */}
      {!hasMore && events.length > 0 && (
        <p className="text-xs text-muted-foreground text-center py-4">
          -- Showing last 30 days --
        </p>
      )}
    </div>
  )
}

// --- Event Row ---

function EventRow({
  event,
  isNew,
}: {
  event: ActivityEvent
  isNew: boolean
}) {
  const Icon = EVENT_ICONS[event.event_type as EventType]
  const description = formatEventDescription(event)
  const chip = getMetadataChip(event)
  const timestamp = formatTimelineTimestamp(event.created_at)
  const fullTimestamp = formatFullTimestamp(event.created_at)

  return (
    <div
      className={`flex items-center gap-3 h-10 px-2 rounded-md transition-colors duration-150 hover:bg-muted/50 ${
        isNew ? 'animate-event-enter' : ''
      }`}
    >
      {/* Icon */}
      {Icon && <Icon className="h-4 w-4 text-muted-foreground shrink-0" />}

      {/* Description + chip */}
      <span className="text-sm text-foreground truncate">
        {description}
        {chip && (
          <>
            <span className="text-muted-foreground mx-1.5">&middot;</span>
            <span className="text-xs bg-muted rounded px-1.5 py-0.5 font-mono">
              {chip}
            </span>
          </>
        )}
      </span>

      {/* Timestamp */}
      <span
        className="font-mono text-xs text-muted-foreground ml-auto whitespace-nowrap shrink-0"
        title={fullTimestamp}
      >
        {timestamp}
      </span>
    </div>
  )
}
