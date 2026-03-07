'use client'

import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { Search, Loader2, AlertCircle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { formatRelativeTime } from '@/lib/utils'
import {
  type ContextPageRow,
  type GenerationState,
  STATUS_COLORS,
  FILTER_OPTIONS,
  type StatusFilter,
  fetchContextPages,
} from '@/lib/context-feed'
import { useContextPagesRealtime } from '@/hooks/use-context-pages-realtime'
import {
  apiFetchSSE,
  SOURCE_LABELS,
  searchLinearTickets,
  type LinearTicketSearchResult,
} from '@/lib/api'
import { GenerationProgress } from '@/components/generation-progress'
import type { RealtimePostgresChangesPayload } from '@supabase/supabase-js'

type RowPayload = RealtimePostgresChangesPayload<Record<string, unknown>>

// ---------------------------------------------------------------------------
// useDebounce hook
// ---------------------------------------------------------------------------

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return debouncedValue
}

// ---------------------------------------------------------------------------
// Context Feed Page
// ---------------------------------------------------------------------------

export default function ContextFeedPage() {
  const router = useRouter()

  // State management
  const [pages, setPages] = useState<ContextPageRow[]>([])
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showGenerateForm, setShowGenerateForm] = useState(false)
  const [generateTicketId, setGenerateTicketId] = useState('')

  // SSE generation progress state
  const [generation, setGeneration] = useState<GenerationState | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  // Ticket search state
  const [ticketResults, setTicketResults] = useState<LinearTicketSearchResult[]>([])
  const [loadingTickets, setLoadingTickets] = useState(false)
  const [showTicketDropdown, setShowTicketDropdown] = useState(false)
  const searchContainerRef = useRef<HTMLDivElement>(null)
  const ticketSearchRef = useRef<NodeJS.Timeout | null>(null)

  const debouncedQuery = useDebounce(searchQuery, 200)

  // Initial fetch
  const loadPages = useCallback(async () => {
    setError(null)
    setIsLoading(true)
    try {
      const data = await fetchContextPages()
      setPages(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load context pages')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadPages()
  }, [loadPages])

  // Realtime subscription
  useContextPagesRealtime({
    onInsert: useCallback((payload: RowPayload) => {
      const newRow = payload.new as ContextPageRow
      if (newRow?.id) {
        setPages((prev) => [newRow, ...prev])
      }
    }, []),
    onUpdate: useCallback((payload: RowPayload) => {
      const updated = payload.new as ContextPageRow
      if (updated?.id) {
        setPages((prev) =>
          prev.map((p) => (p.id === updated.id ? { ...p, ...updated } : p))
        )
      }
    }, []),
  })

  // Load tickets (empty query = assigned tickets, like onboarding)
  const loadTickets = useCallback(async (query?: string) => {
    setLoadingTickets(true)
    try {
      const result = await searchLinearTickets(query, 5)
      setTicketResults(result.tickets)
    } catch {
      setTicketResults([])
    } finally {
      setLoadingTickets(false)
    }
  }, [])

  // Debounced search on query changes (skip initial)
  const isInitialTicketLoad = useRef(true)
  useEffect(() => {
    if (!showTicketDropdown) {
      isInitialTicketLoad.current = true
      return
    }
    if (isInitialTicketLoad.current) {
      isInitialTicketLoad.current = false
      return
    }
    if (ticketSearchRef.current) clearTimeout(ticketSearchRef.current)
    ticketSearchRef.current = setTimeout(() => {
      loadTickets(searchQuery.trim() || undefined)
    }, 300)
    return () => {
      if (ticketSearchRef.current) clearTimeout(ticketSearchRef.current)
    }
  }, [searchQuery, showTicketDropdown, loadTickets])

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (searchContainerRef.current && !searchContainerRef.current.contains(e.target as Node)) {
        setShowTicketDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Shared SSE generation trigger
  const startGeneration = useCallback((ticketIdentifier: string, linearIssueId?: string) => {
    // Cancel any existing stream
    abortRef.current?.abort()

    // Initialize generation state with empty steps (populated on 'start' event)
    setGeneration({
      ticket: ticketIdentifier,
      steps: [],
      status: 'streaming',
    })

    const streamPath = linearIssueId
      ? `/api/context/${encodeURIComponent(ticketIdentifier)}/generate-stream?linear_issue_id=${encodeURIComponent(linearIssueId)}`
      : `/api/context/${encodeURIComponent(ticketIdentifier)}/generate-stream`

    const controller = apiFetchSSE(
      streamPath,
      (event) => {
        // Use functional setState to avoid stale closures
        setGeneration((prev) => {
          if (!prev) return prev

          switch (event.event) {
            case 'start':
              return {
                ...prev,
                steps: event.steps.map((source) => ({
                  source,
                  label: SOURCE_LABELS[source] || source,
                  status: 'waiting' as const,
                })),
              }

            case 'step_start':
              return {
                ...prev,
                steps: prev.steps.map((s) =>
                  s.source === event.source
                    ? { ...s, status: 'active' as const, detail: 'Searching...' }
                    : s
                ),
              }

            case 'step_complete':
              return {
                ...prev,
                steps: prev.steps.map((s) =>
                  s.source === event.source
                    ? { ...s, status: 'complete' as const, count: event.count, detail: event.detail }
                    : s
                ),
              }

            case 'step_error':
              return {
                ...prev,
                steps: prev.steps.map((s) =>
                  s.source === event.source
                    ? { ...s, status: 'error' as const, detail: event.error }
                    : s
                ),
                status: 'error',
                errorMessage: event.error,
              }

            case 'complete':
              return {
                ...prev,
                status: 'complete',
                contextPageId: event.context_page_id,
              }

            case 'error':
              return {
                ...prev,
                status: 'error',
                errorMessage: event.message,
              }

            default:
              return prev
          }
        })
      },
      (error) => {
        setGeneration((prev) =>
          prev ? { ...prev, status: 'error', errorMessage: error.message } : prev
        )
      }
    )

    abortRef.current = controller
  }, [])

  // Handle completion with collapse + auto-navigate
  useEffect(() => {
    if (generation?.status === 'complete' && generation.contextPageId) {
      // Brief pause to show all-green checkmarks, then collapse
      const showTimer = setTimeout(() => {
        setGeneration((prev) => prev ? { ...prev, status: 'collapsing' } : prev)
      }, 1200) // Show completed state for 1.2s

      return () => clearTimeout(showTimer)
    }
  }, [generation?.status, generation?.contextPageId])

  useEffect(() => {
    if (generation?.status === 'collapsing' && generation.contextPageId) {
      // After collapse animation, navigate
      const navTimer = setTimeout(() => {
        router.push(`/dashboard/context/${generation.contextPageId}`)
        setGeneration(null)
      }, 500) // Match progress-collapse animation duration

      return () => clearTimeout(navTimer)
    }
  }, [generation?.status, generation?.contextPageId, router])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  // Generate context for a ticket from search results
  const handleGenerateFromSearch = useCallback(
    (ticket: LinearTicketSearchResult) => {
      setShowTicketDropdown(false)
      setSearchQuery('')
      startGeneration(ticket.identifier, ticket.id)
    },
    [startGeneration]
  )

  // Filtering logic
  const filteredPages = useMemo(() => {
    let result = pages

    if (statusFilter !== 'all') {
      result = result.filter((page) => page.status === statusFilter)
    }

    const q = debouncedQuery.trim().toLowerCase()
    if (q) {
      result = result.filter(
        (page) =>
          page.title.toLowerCase().includes(q) ||
          page.ticket_identifier?.toLowerCase().includes(q)
      )
    }

    return result
  }, [pages, statusFilter, debouncedQuery])

  // Whether any filter/search is active
  const hasActiveFilters = statusFilter !== 'all' || debouncedQuery.trim().length > 0

  // Generate handler (manual form)
  const handleGenerate = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault()
      const ticketId = generateTicketId.trim().toUpperCase()
      if (!ticketId) return
      setGenerateTicketId('')
      setShowGenerateForm(false)
      startGeneration(ticketId)
    },
    [generateTicketId, startGeneration]
  )

  // Clear filters handler
  const clearFilters = useCallback(() => {
    setStatusFilter('all')
    setSearchQuery('')
  }, [])

  // -----------------------------------------------------------------------
  // Loading skeleton
  // -----------------------------------------------------------------------
  if (isLoading) {
    return (
      <div className="space-y-6 animate-fade-in-up">
        {/* Section label skeleton */}
        <Skeleton className="h-3 w-28" />

        {/* Filter pills skeleton */}
        <div className="flex gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-4 w-16" />
          ))}
        </div>

        {/* Search skeleton */}
        <Skeleton className="h-9 w-full max-w-sm" />

        {/* List skeleton */}
        <div className="rounded-xl border border-border overflow-hidden divide-y divide-border">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="px-4 py-3 space-y-1.5">
              <div className="flex items-center justify-between">
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-1.5 w-1.5 rounded-full" />
              </div>
              <div className="flex items-center gap-3">
                <Skeleton className="h-3 w-16" />
                <Skeleton className="h-3 w-12" />
                <Skeleton className="h-3 w-16" />
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  // -----------------------------------------------------------------------
  // Error state
  // -----------------------------------------------------------------------
  if (error) {
    return (
      <div className="space-y-6 animate-fade-in-up">
        <h3 className="section-label mb-3">Context Feed</h3>
        <div className="flex items-center gap-3 rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm animate-scale-in">
          <AlertCircle className="h-4 w-4 shrink-0 text-destructive" />
          <span className="flex-1 text-destructive">{error}</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={loadPages}
            className="h-7 gap-1.5 text-destructive hover:text-destructive"
          >
            <RefreshCw className="h-3 w-3" />
            Retry
          </Button>
        </div>
      </div>
    )
  }

  // -----------------------------------------------------------------------
  // Main render
  // -----------------------------------------------------------------------
  return (
    <div className="space-y-6 animate-fade-in-up">
      {/* Section label */}
      <h3 className="section-label mb-3">Context Feed</h3>

      {/* Status filter pills */}
      <div className="flex gap-4">
        {FILTER_OPTIONS.map((option) => (
          <button
            key={option}
            onClick={() => setStatusFilter(option)}
            className={`relative pb-1.5 text-sm font-medium transition-colors duration-150 ${
              statusFilter === option
                ? 'text-primary'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {option.charAt(0).toUpperCase() + option.slice(1)}
            {statusFilter === option && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary rounded-full" />
            )}
          </button>
        ))}
      </div>

      {/* Search input with ticket dropdown */}
      <div className="relative max-w-sm" ref={searchContainerRef}>
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search tickets or filter by title..."
          value={searchQuery}
          onChange={(e) => {
            setSearchQuery(e.target.value)
            setShowTicketDropdown(true)
          }}
          onFocus={() => {
            setShowTicketDropdown(true)
            loadTickets(searchQuery.trim() || undefined)
          }}
          className="pl-9"
        />

        {/* Ticket search dropdown */}
        {showTicketDropdown && (
          <div className="absolute top-full left-0 right-0 mt-1 z-50 rounded-lg border border-border bg-popover shadow-md overflow-hidden">
            {loadingTickets ? (
              <div className="p-3 space-y-2">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <Skeleton className="h-4 w-14 shrink-0" />
                    <Skeleton className="h-4 w-full" />
                  </div>
                ))}
              </div>
            ) : ticketResults.length > 0 ? (
              <div>
                <div className="px-3 py-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  {searchQuery.trim() ? 'Linear tickets' : 'Your tickets'}
                </div>
                {ticketResults.map((ticket) => (
                  <button
                    key={ticket.id}
                    onClick={() => handleGenerateFromSearch(ticket)}
                    className="flex w-full items-start gap-3 px-3 py-2 text-left transition-colors hover:bg-muted/50"
                  >
                    <span className="shrink-0 font-mono text-xs font-medium text-primary mt-0.5">
                      {ticket.identifier}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-foreground truncate">
                        {ticket.title}
                      </p>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        {ticket.state && <span>{ticket.state}</span>}
                        {ticket.assignee && (
                          <>
                            <span className="text-border">·</span>
                            <span>{ticket.assignee}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <p className="px-3 py-4 text-center text-sm text-muted-foreground">
                {searchQuery.trim() ? 'No tickets found' : 'No assigned tickets found'}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Feed list / empty states */}
      {(filteredPages.length > 0 || generation) ? (
        /* Populated feed */
        <div className="rounded-xl border bg-card overflow-hidden divide-y divide-border stagger-children">
          {/* Active generation progress -- always at top */}
          {generation && (
            <GenerationProgress
              ticketIdentifier={generation.ticket}
              steps={generation.steps}
              status={generation.status}
              errorMessage={generation.errorMessage}
              onRetry={() => startGeneration(generation.ticket)}
              onDismiss={() => {
                abortRef.current?.abort()
                setGeneration(null)
              }}
            />
          )}

          {/* Existing feed rows */}
          {filteredPages.map((page) => (
            <button
              key={page.id}
              onClick={() => router.push(`/dashboard/context/${page.id}`)}
              className={`w-full text-left px-4 py-3 transition-colors duration-150 hover:bg-muted/40 border-l-2 ${
                STATUS_COLORS[page.status]?.border ?? 'border-l-transparent'
              }`}
            >
              {/* Line 1: title + status dot */}
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium text-foreground truncate">
                  {page.title}
                </span>
                <span
                  className={`shrink-0 h-1.5 w-1.5 rounded-full ${
                    STATUS_COLORS[page.status]?.dot ?? 'bg-muted-foreground/30'
                  }`}
                />
              </div>
              {/* Line 2: ticket ID + relative time + source count */}
              <div className="flex items-center gap-3 mt-0.5">
                {page.ticket_identifier && (
                  <span className="text-xs font-mono text-muted-foreground">
                    {page.ticket_identifier}
                  </span>
                )}
                <span className="text-xs text-muted-foreground">
                  {formatRelativeTime(page.updated_at)}
                </span>
                <span className="text-xs text-muted-foreground">
                  {page.sources?.length ?? 0} sources
                </span>
              </div>
            </button>
          ))}
        </div>
      ) : hasActiveFilters ? (
        /* Filtered empty state */
        <div className="rounded-xl border bg-card overflow-hidden">
          <div className="flex flex-col items-center gap-3 py-12 px-4 text-center">
            <p className="text-sm text-muted-foreground">
              No pages match your filters
            </p>
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              Clear filters
            </Button>
          </div>
        </div>
      ) : (
        /* True empty state */
        <div className="rounded-xl border bg-card overflow-hidden divide-y divide-border">
          {/* Skeleton preview rows */}
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="px-4 py-3 space-y-1.5 opacity-40">
              <div className="flex items-center justify-between">
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-1.5 w-1.5 rounded-full" />
              </div>
              <div className="flex items-center gap-3">
                <Skeleton className="h-3 w-16" />
                <Skeleton className="h-3 w-12" />
                <Skeleton className="h-3 w-16" />
              </div>
            </div>
          ))}

          {/* CTA section */}
          <div className="flex flex-col items-center gap-2 py-8 px-4 text-center">
            <p className="text-sm font-medium text-muted-foreground">
              No context pages yet
            </p>
            <p className="text-xs text-muted-foreground">
              Generate context for a ticket to see it here.
            </p>

            {!showGenerateForm ? (
              <Button
                className="mt-2"
                onClick={() => setShowGenerateForm(true)}
              >
                Generate Context
              </Button>
            ) : (
              <form
                onSubmit={handleGenerate}
                className="flex items-center gap-2 mt-2 w-full max-w-xs"
              >
                <Input
                  placeholder="Enter ticket ID (e.g. CON-16)"
                  value={generateTicketId}
                  onChange={(e) => setGenerateTicketId(e.target.value)}
                  disabled={generation !== null}
                  autoFocus
                />
                <Button type="submit" disabled={generation !== null || !generateTicketId.trim()}>
                  {generation !== null ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    'Generate'
                  )}
                </Button>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
