'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  searchLinearTickets,
  apiFetchSSE,
  SOURCE_LABELS,
  type LinearTicketSearchResult,
} from '@/lib/api'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { GenerationProgress } from '@/components/generation-progress'
import type { GenerationState } from '@/lib/context-feed'

interface StepContextProps {
  onComplete: () => void
  onMarkComplete?: () => Promise<void>
}

type StepState = 'intro' | 'picking' | 'generating' | 'ready' | 'error'

const PRIORITY_LABELS: Record<number, string> = {
  0: 'None',
  1: 'Urgent',
  2: 'High',
  3: 'Normal',
  4: 'Low',
}

export function StepContext({ onComplete, onMarkComplete }: StepContextProps) {
  const router = useRouter()
  const [state, setState] = useState<StepState>('intro')
  const [generation, setGeneration] = useState<GenerationState | null>(null)

  // Ticket picker state
  const [tickets, setTickets] = useState<LinearTicketSearchResult[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [loadingTickets, setLoadingTickets] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [endCursor, setEndCursor] = useState<string | null>(null)
  const [hasNextPage, setHasNextPage] = useState(false)
  const [selectedTicket, setSelectedTicket] = useState<LinearTicketSearchResult | null>(null)
  const debounceRef = useRef<NodeJS.Timeout | null>(null)
  const observerRef = useRef<IntersectionObserver | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  // Cleanup SSE stream on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  // Auto-navigate to context detail page on completion
  useEffect(() => {
    if (generation?.status === 'complete' && generation.contextPageId) {
      const timer = setTimeout(async () => {
        await onMarkComplete?.()
        router.push(`/dashboard/context/${generation.contextPageId}`)
      }, 1200)
      return () => clearTimeout(timer)
    }
  }, [generation?.status, generation?.contextPageId, onMarkComplete, router])

  // Load assigned tickets when entering picker
  const loadTickets = useCallback(async (query?: string, cursor?: string) => {
    if (cursor) {
      setLoadingMore(true)
    } else {
      setLoadingTickets(true)
    }
    try {
      const result = await searchLinearTickets(query, 20, cursor)
      if (cursor) {
        setTickets((prev) => [...prev, ...result.tickets])
      } else {
        setTickets(result.tickets)
      }
      setHasNextPage(result.has_next_page)
      setEndCursor(result.end_cursor)
    } catch {
      if (!cursor) setTickets([])
    } finally {
      setLoadingTickets(false)
      setLoadingMore(false)
    }
  }, [])

  const enterPicker = useCallback(() => {
    setState('picking')
    loadTickets()
  }, [loadTickets])

  // Debounced search — only fires on query changes, not on initial mount
  const isInitialMount = useRef(true)
  useEffect(() => {
    if (state !== 'picking') {
      isInitialMount.current = true
      return
    }
    if (isInitialMount.current) {
      isInitialMount.current = false
      return
    }
    setHasNextPage(false)
    setEndCursor(null)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      loadTickets(searchQuery || undefined)
    }, 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [searchQuery, state, loadTickets])

  // Infinite scroll — ref callback attaches observer when sentinel mounts
  const loadingMoreRef = useRef(loadingMore)
  const endCursorRef = useRef(endCursor)
  const searchQueryRef = useRef(searchQuery)
  loadingMoreRef.current = loadingMore
  endCursorRef.current = endCursor
  searchQueryRef.current = searchQuery

  const sentinelRef = useCallback(
    (node: HTMLDivElement | null) => {
      if (observerRef.current) {
        observerRef.current.disconnect()
        observerRef.current = null
      }
      if (!node) return
      observerRef.current = new IntersectionObserver(
        (entries) => {
          if (entries[0]?.isIntersecting && !loadingMoreRef.current) {
            loadTickets(searchQueryRef.current || undefined, endCursorRef.current ?? undefined)
          }
        },
        { threshold: 0 }
      )
      observerRef.current.observe(node)
    },
    [loadTickets]
  )

  const generateForTicket = useCallback((ticket: LinearTicketSearchResult) => {
    abortRef.current?.abort()
    setSelectedTicket(ticket)
    setState('generating')

    const gen: GenerationState = {
      ticket: ticket.identifier,
      steps: [],
      status: 'streaming',
    }
    setGeneration(gen)

    const streamPath = `/api/context/${encodeURIComponent(ticket.identifier)}/generate-stream?linear_issue_id=${encodeURIComponent(ticket.id)}`

    const controller = apiFetchSSE(
      streamPath,
      (event) => {
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
              return { ...prev, status: 'complete', contextPageId: event.context_page_id }
            case 'error':
              return { ...prev, status: 'error', errorMessage: event.message }
            default:
              return prev
          }
        })
      },
      (error) => {
        setGeneration((prev) =>
          prev ? { ...prev, status: 'error', errorMessage: error.message } : prev
        )
        setState('error')
      }
    )

    abortRef.current = controller
  }, [])

  // Intro state
  if (state === 'intro') {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold text-foreground">
            Generate your first context page
          </h2>
          <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
            ContextOS pulls context from your tickets, discussions, and docs to
            generate a rich prompt for every task. Pick a ticket to see it in
            action.
          </p>
        </div>

        <div className="space-y-3">
          <Button onClick={enterPicker} className="w-full">
            Choose a ticket
          </Button>
          <button
            onClick={onComplete}
            className="w-full text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Skip for now
          </button>
        </div>
      </div>
    )
  }

  // Ticket picker state
  if (state === 'picking') {
    return (
      <div className="space-y-4">
        <div>
          <h2 className="text-xl font-semibold text-foreground">
            Pick a ticket
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Search your Linear tickets or pick from your assigned issues
          </p>
        </div>

        <Input
          placeholder="Search tickets..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          autoFocus
        />

        <div className="max-h-[280px] overflow-y-auto space-y-1.5">
          {loadingTickets ? (
            <div className="space-y-2 py-2">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="flex items-center gap-3 px-3 py-2">
                  <Skeleton className="h-4 w-14 shrink-0" />
                  <Skeleton className="h-4 w-full" />
                </div>
              ))}
            </div>
          ) : tickets.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              {searchQuery ? 'No tickets found' : 'No assigned tickets found'}
            </p>
          ) : (
            <>
              {tickets.map((ticket) => (
                <button
                  key={ticket.id}
                  onClick={() => generateForTicket(ticket)}
                  className="flex w-full items-start gap-3 rounded-md px-3 py-2.5 text-left transition-colors hover:bg-muted/50"
                >
                  <span className="shrink-0 font-mono text-xs font-medium text-primary mt-0.5">
                    {ticket.identifier}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-foreground truncate">
                      {ticket.title}
                    </p>
                    <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                      {ticket.state && <span>{ticket.state}</span>}
                      {ticket.assignee && (
                        <>
                          <span className="text-border">·</span>
                          <span>{ticket.assignee}</span>
                        </>
                      )}
                      {ticket.priority != null && ticket.priority > 0 && (
                        <>
                          <span className="text-border">·</span>
                          <span>{PRIORITY_LABELS[ticket.priority] ?? ''}</span>
                        </>
                      )}
                    </div>
                  </div>
                </button>
              ))}
              {hasNextPage && (
                <div ref={sentinelRef} className="px-3 py-2 text-xs text-center text-muted-foreground">
                  {loadingMore ? 'Loading...' : ''}
                </div>
              )}
            </>
          )}
        </div>

        <button
          onClick={onComplete}
          className="w-full text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          Skip for now
        </button>
      </div>
    )
  }

  // Generating / complete / error — all use SSE live progress
  if (state === 'generating' || state === 'ready' || state === 'error') {
    const genStatus = generation?.status
    const isComplete = genStatus === 'complete'
    const isError = genStatus === 'error' || state === 'error'

    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold text-foreground">
            {isComplete
              ? 'Your first context page'
              : isError
                ? "Couldn\u2019t generate context"
                : 'Generating context'}
          </h2>
          {selectedTicket && (
            <p className="mt-1 text-sm text-muted-foreground">
              <span className="font-mono font-medium text-primary">
                {selectedTicket.identifier}
              </span>{' '}
              {selectedTicket.title}
            </p>
          )}
        </div>

        {generation && (
          <GenerationProgress
            ticketIdentifier={generation.ticket}
            steps={generation.steps}
            status={generation.status}
            errorMessage={generation.errorMessage}
            onRetry={
              selectedTicket
                ? () => generateForTicket(selectedTicket)
                : undefined
            }
            onDismiss={() => {
              abortRef.current?.abort()
              enterPicker()
            }}
          />
        )}

        <div className="space-y-3">
          {isError && (
            <>
              <Button onClick={enterPicker} variant="outline" className="w-full">
                Try another ticket
              </Button>
              <Button onClick={onComplete} className="w-full">
                Continue to dashboard
              </Button>
            </>
          )}
        </div>
      </div>
    )
  }

  // Fallback — should not be reached
  return null
}
