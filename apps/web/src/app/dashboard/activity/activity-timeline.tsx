'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Clock, ArrowUp, Zap, ChevronDown, Lightbulb, CircleCheck, Tag } from 'lucide-react'
import Link from 'next/link'
import { createClient } from '@/lib/supabase/client'
import { Skeleton } from '@/components/ui/skeleton'
import type { ActivityEvent, EventType } from './types'
import { EVENT_ICONS, INTEGRATION_COLORS, getEventCategory } from './types'
import {
  formatEventDescription,
  getEventSubtitle,
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
          }, 600)

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
            header.classList.add('border-b', 'border-border/50')
          } else {
            header.classList.remove('border-b', 'border-border/50')
          }
        }
      },
      { threshold: 0 }
    )

    sentinels.forEach((s) => observer.observe(s))
    return () => observer.disconnect()
  }, [events.length])

  const eventsRef = useRef(events)
  eventsRef.current = events

  const loadMore = useCallback(async () => {
    if (!hasMore || isLoadingMore) return
    setIsLoadingMore(true)

    const oldest = eventsRef.current[eventsRef.current.length - 1]
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
  }, [hasMore, isLoadingMore, workspaceId])

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
  }, [hasMore, isLoadingMore, loadMore])

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
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <div className="relative mb-6">
          <div className="h-12 w-12 rounded-2xl bg-muted/60 flex items-center justify-center">
            <Clock className="h-5 w-5 text-muted-foreground" />
          </div>
          <div className="absolute -top-1 -right-1 h-3 w-3 rounded-full bg-primary/20 animate-pulse" />
        </div>
        <h2 className="text-sm font-medium text-foreground">No activity yet</h2>
        <p className="text-xs text-muted-foreground max-w-[280px] mx-auto mt-1.5 leading-relaxed">
          Events will appear here as you connect integrations and sync your data.
        </p>
        <Link
          href="/dashboard/settings?tab=integrations"
          className="text-xs text-primary/70 hover:text-primary transition-colors mt-4"
        >
          Connect an integration
        </Link>
      </div>
    )
  }

  const dayGroups = groupEventsByDay(events)

  return (
    <div ref={timelineRef} className="relative animate-fade-in-up">
      {/* New events banner */}
      {bufferedEvents.length > 0 && (
        <div className="sticky top-0 z-20 flex justify-center py-2">
          <button
            onClick={flushBuffer}
            className="inline-flex items-center gap-1.5 bg-primary/10 backdrop-blur-md text-xs font-medium text-primary rounded-full px-3.5 py-1.5 animate-banner-slide-in cursor-pointer hover:bg-primary/15 transition-colors duration-150 shadow-sm"
          >
            <ArrowUp className="h-3 w-3" />
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
          <div className="section-label sticky top-0 z-10 bg-background/95 backdrop-blur-sm pt-6 pb-3 transition-[border] duration-150">
            {group.label}
          </div>
          <div className="rounded-xl border border-border/70 bg-card overflow-hidden divide-y divide-border/40">
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
        <div className="mt-4">
          <div className="rounded-xl border border-border/50 bg-card overflow-hidden divide-y divide-border/30">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={`sk-${i}`} className="flex items-center gap-3 px-4 py-3">
                <Skeleton className="h-7 w-7 rounded-lg shrink-0" />
                <div className="flex-1 space-y-1.5">
                  <Skeleton className="h-3.5 w-48" />
                  <Skeleton className="h-2.5 w-24" />
                </div>
                <Skeleton className="h-3 w-12 ml-auto" />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* End of list */}
      {!hasMore && events.length > 0 && (
        <div className="flex items-center gap-3 py-8 justify-center">
          <div className="h-px flex-1 max-w-16 bg-border/40" />
          <span className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground/40">
            30 day history
          </span>
          <div className="h-px flex-1 max-w-16 bg-border/40" />
        </div>
      )}
    </div>
  )
}

// --- Shared helpers ---

function useEventData(event: ActivityEvent) {
  const integration = event.metadata.integration as string | undefined
  return {
    Icon: EVENT_ICONS[event.event_type as EventType],
    description: formatEventDescription(event),
    timestamp: formatTimelineTimestamp(event.created_at),
    fullTimestamp: formatFullTimestamp(event.created_at),
    brandColor: integration ? INTEGRATION_COLORS[integration] : undefined,
  }
}

function EventIcon({
  Icon,
  bgClass,
  colorClass,
  brandColor,
}: {
  Icon: (typeof EVENT_ICONS)[EventType]
  bgClass: string
  colorClass: string
  brandColor?: string
}) {
  return (
    <div className={`shrink-0 h-7 w-7 rounded-lg ${bgClass} flex items-center justify-center`}>
      <Icon
        className={`h-3.5 w-3.5 ${colorClass}`}
        style={brandColor ? { color: brandColor } : undefined}
      />
    </div>
  )
}

function Timestamp({ timestamp, fullTimestamp }: { timestamp: string; fullTimestamp: string }) {
  return (
    <span
      className="font-mono text-[11px] text-muted-foreground/50 ml-auto whitespace-nowrap shrink-0 tabular-nums"
      title={fullTimestamp}
    >
      {timestamp}
    </span>
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
  const category = getEventCategory(event.event_type as EventType)

  if (category === 'digest') {
    return <DigestRow event={event} isNew={isNew} />
  }

  return <StandardRow event={event} isNew={isNew} category={category} />
}

function StandardRow({
  event,
  isNew,
  category,
}: {
  event: ActivityEvent
  isNew: boolean
  category: import('./types').EventCategory
}) {
  const { Icon, description, timestamp, fullTimestamp, brandColor } = useEventData(event)
  const subtitle = getEventSubtitle(event)
  const isError = event.metadata.error === true

  const iconBgClass = isError
    ? 'bg-destructive/10'
    : category === 'content'
      ? 'bg-primary/8'
      : 'bg-muted/60'

  const iconColorClass = isError
    ? 'text-destructive'
    : !brandColor
      ? category === 'content'
        ? 'text-primary/70'
        : 'text-muted-foreground'
      : ''

  return (
    <div
      className={`flex items-center gap-3 px-4 py-2.5 transition-colors duration-150 hover:bg-muted/30 ${
        isNew ? 'animate-event-enter' : ''
      } ${isError ? 'bg-destructive/[0.02]' : ''}`}
    >
      <EventIcon Icon={Icon} bgClass={iconBgClass} colorClass={iconColorClass} brandColor={!isError ? brandColor : undefined} />

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm text-foreground truncate">
            {description}
          </span>
          {isError && (
            <span className="text-[10px] font-medium bg-destructive/10 text-destructive rounded px-1.5 py-0.5 shrink-0 uppercase tracking-wider">
              failed
            </span>
          )}
        </div>
        {subtitle && (
          <p className="text-xs text-muted-foreground/70 truncate mt-0.5 font-mono">
            {subtitle}
          </p>
        )}
      </div>

      <Timestamp timestamp={timestamp} fullTimestamp={fullTimestamp} />
    </div>
  )
}

interface DigestDecision {
  title: string
  rationale: string
  participants: string[]
}

interface DigestActionItem {
  description: string
  assignee: string | null
}

interface DigestTopic {
  title: string
  ticket_refs: string[]
}

function DigestRow({
  event,
  isNew,
}: {
  event: ActivityEvent
  isNew: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const { Icon, description, timestamp, fullTimestamp, brandColor } = useEventData(event)
  const summary = event.metadata.summary as string | undefined
  const topChannels = event.metadata.top_channels as string[] | undefined
  const decisions = Array.isArray(event.metadata.decisions)
    ? (event.metadata.decisions as DigestDecision[])
    : undefined
  const actionItems = Array.isArray(event.metadata.action_items)
    ? (event.metadata.action_items as DigestActionItem[])
    : undefined
  const topics = Array.isArray(event.metadata.topics)
    ? (event.metadata.topics as DigestTopic[])
    : undefined

  const hasStructuredData = (decisions && decisions.length > 0)
    || (actionItems && actionItems.length > 0)
    || (topics && topics.length > 0)

  // Quick stats for the collapsed view
  const stats: string[] = []
  if (decisions?.length) stats.push(`${decisions.length} decision${decisions.length > 1 ? 's' : ''}`)
  if (actionItems?.length) stats.push(`${actionItems.length} action${actionItems.length > 1 ? 's' : ''}`)
  if (topics?.length) stats.push(`${topics.length} topic${topics.length > 1 ? 's' : ''}`)

  return (
    <div
      className={`px-4 py-3 transition-colors duration-150 hover:bg-muted/30 ${
        isNew ? 'animate-event-enter' : ''
      }`}
    >
      {/* Header */}
      <div className="flex items-center gap-3">
        <EventIcon Icon={Icon} bgClass="bg-primary/8" colorClass="text-primary/70" brandColor={brandColor} />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm text-foreground truncate">
              {description}
            </span>
            <span className="inline-flex items-center gap-0.5 text-[10px] font-medium bg-primary/8 text-primary/70 rounded px-1.5 py-0.5 shrink-0">
              <Zap className="h-2.5 w-2.5" />
              digest
            </span>
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            {topChannels && topChannels.length > 0 && (
              <span className="text-xs text-muted-foreground/50 font-mono truncate">
                {topChannels.join(', ')}
              </span>
            )}
            {stats.length > 0 && (
              <>
                {topChannels && topChannels.length > 0 && (
                  <span className="text-muted-foreground/30">·</span>
                )}
                <span className="text-xs text-muted-foreground/50">
                  {stats.join(' · ')}
                </span>
              </>
            )}
          </div>
        </div>

        <Timestamp timestamp={timestamp} fullTimestamp={fullTimestamp} />
      </div>

      {/* Expandable content */}
      {(summary || hasStructuredData) && (
        <div className="mt-2.5 ml-10">
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-xs text-muted-foreground/60 hover:text-muted-foreground transition-colors cursor-pointer"
          >
            <ChevronDown
              className={`h-3 w-3 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
            />
            {expanded ? 'Collapse' : 'View details'}
          </button>

          {expanded && (
            <div className="mt-3 space-y-3 animate-fade-in-up">
              {/* Decisions */}
              {decisions && decisions.length > 0 && (
                <div>
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <Lightbulb className="h-3 w-3 text-amber-500/70" />
                    <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground/60">
                      Decisions
                    </span>
                  </div>
                  <div className="space-y-1.5">
                    {decisions.map((d, i) => (
                      <div key={i} className="rounded-lg bg-amber-500/[0.04] border border-amber-500/10 px-3 py-2">
                        <p className="text-sm text-foreground">{d.title}</p>
                        <p className="text-xs text-muted-foreground/60 mt-0.5">{d.rationale}</p>
                        {Array.isArray(d.participants) && d.participants.length > 0 && (
                          <div className="flex items-center gap-1 mt-1">
                            {d.participants.map((p) => (
                              <span key={p} className="text-[10px] bg-muted/60 rounded px-1.5 py-0.5 text-muted-foreground">
                                {p}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Action items */}
              {actionItems && actionItems.length > 0 && (
                <div>
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <CircleCheck className="h-3 w-3 text-primary/60" />
                    <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground/60">
                      Action Items
                    </span>
                  </div>
                  <div className="space-y-1">
                    {actionItems.map((a, i) => (
                      <div key={i} className="flex items-start gap-2 text-sm">
                        <span className="text-muted-foreground/40 shrink-0">—</span>
                        <span className="text-foreground/80">{a.description}</span>
                        {a.assignee && (
                          <span className="text-[10px] bg-primary/8 text-primary/70 rounded px-1.5 py-0.5 shrink-0 ml-auto">
                            {a.assignee}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Topics */}
              {topics && topics.length > 0 && (
                <div>
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <Tag className="h-3 w-3 text-muted-foreground/50" />
                    <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground/60">
                      Topics
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {topics.map((t, i) => (
                      <span key={i} className="text-xs bg-muted/50 rounded-md px-2 py-0.5 text-foreground/70">
                        {t.title}
                        {Array.isArray(t.ticket_refs) && t.ticket_refs.length > 0 && (
                          <span className="ml-1 text-muted-foreground/50 font-mono text-[10px]">
                            {t.ticket_refs.join(', ')}
                          </span>
                        )}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Prose summary */}
              {summary && (
                <div className="text-sm text-foreground/70 leading-relaxed whitespace-pre-line border-t border-border/30 pt-2.5">
                  {summary}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
