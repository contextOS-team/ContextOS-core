'use client'

import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'
import {
  Search,
  AlertCircle,
  RefreshCw,
  Plus,
  MessageSquare,
  Code2,
  GitPullRequest,
  Video,
  FileText,
  CheckCircle2,
  Zap,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { formatRelativeTime } from '@/lib/utils'
import {
  type ContextPageRow,
  STATUS_COLORS,
  FILTER_OPTIONS,
  type StatusFilter,
  fetchContextPages,
} from '@/lib/context-feed'
import { useContextPagesRealtime } from '@/hooks/use-context-pages-realtime'
import {
  searchLinearTickets,
  searchJiraIssues,
  getIntegrationStatus,
} from '@/lib/api'
import { detectTicketProvider } from '@/lib/ticket-provider'
import type { RealtimePostgresChangesPayload } from '@supabase/supabase-js'

type RowPayload = RealtimePostgresChangesPayload<Record<string, unknown>>

// ---------------------------------------------------------------------------
// Source type → group mapping for chips
// ---------------------------------------------------------------------------

const SOURCE_GROUPS: Record<string, { group: string; icon: React.ElementType; color: string }> = {
  linear_ticket: { group: 'Linear', icon: CheckCircle2, color: 'text-violet-400 bg-violet-400/10' },
  linear_comment: { group: 'Linear', icon: MessageSquare, color: 'text-violet-400 bg-violet-400/10' },
  slack_message: { group: 'Slack', icon: MessageSquare, color: 'text-pink-400 bg-pink-400/10' },
  meeting_transcript: { group: 'Meetings', icon: Video, color: 'text-amber-400 bg-amber-400/10' },
  meeting_segment: { group: 'Meetings', icon: Video, color: 'text-amber-400 bg-amber-400/10' },
  github_pull_request: { group: 'GitHub', icon: GitPullRequest, color: 'text-emerald-400 bg-emerald-400/10' },
  github_review: { group: 'GitHub', icon: GitPullRequest, color: 'text-emerald-400 bg-emerald-400/10' },
  gitlab_merge_request: { group: 'GitLab', icon: GitPullRequest, color: 'text-orange-400 bg-orange-400/10' },
  gitlab_review: { group: 'GitLab', icon: GitPullRequest, color: 'text-orange-400 bg-orange-400/10' },
  code_chunk: { group: 'Code', icon: Code2, color: 'text-emerald-400 bg-emerald-400/10' },
  notion_page: { group: 'Notion', icon: FileText, color: 'text-blue-400 bg-blue-400/10' },
  jira_issue: { group: 'Jira', icon: CheckCircle2, color: 'text-blue-500 bg-blue-500/10' },
  jira_comment: { group: 'Jira', icon: MessageSquare, color: 'text-blue-500 bg-blue-500/10' },
  telegram_message: { group: 'Telegram', icon: MessageSquare, color: 'text-sky-400 bg-sky-400/10' },
}

function getSourceChips(sources: ContextPageRow['sources']) {
  if (!sources?.length) return []
  const counts: Record<string, { count: number; icon: React.ElementType; color: string }> = {}
  for (const s of sources) {
    const cfg = SOURCE_GROUPS[s.type]
    if (!cfg) continue
    if (!counts[cfg.group]) counts[cfg.group] = { count: 0, icon: cfg.icon, color: cfg.color }
    counts[cfg.group].count++
  }
  return Object.entries(counts).map(([group, { count, icon, color }]) => ({
    group,
    count,
    icon,
    color,
  }))
}

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
// Feed Row
// ---------------------------------------------------------------------------

function FeedRow({ page, onClick }: { page: ContextPageRow; onClick: () => void }) {
  const chips = useMemo(() => getSourceChips(page.sources), [page.sources])
  const colors = STATUS_COLORS[page.status] ?? STATUS_COLORS.draft
  const noSources = !page.sources?.length

  // Strip "Context: " prefix if present
  const displayTitle = page.title.replace(/^Context:\s*/i, '')

  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-4 py-3.5 transition-colors duration-150 hover:bg-muted/40 border-l-2 group ${
        colors.border ?? 'border-l-transparent'
      }`}
    >
      {/* Row 1: title + status */}
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-foreground truncate flex-1">
          {displayTitle}
        </span>
        <span
          className={`shrink-0 h-1.5 w-1.5 rounded-full ${colors.dot}`}
        />
      </div>

      {/* Row 2: metadata + source chips */}
      <div className="flex items-center gap-2 mt-1.5 flex-wrap">
        {page.ticket_identifier && (
          <span className="text-xs font-mono text-muted-foreground">
            {page.ticket_identifier}
          </span>
        )}
        <span className="text-xs text-muted-foreground">
          {formatRelativeTime(page.updated_at)}
        </span>

        {/* Source type chips */}
        {chips.length > 0 ? (
          <div className="flex items-center gap-1 ml-auto">
            {chips.map(({ group, count, icon: Icon, color }) => (
              <span
                key={group}
                className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${color}`}
              >
                <Icon className="h-2.5 w-2.5" />
                {count}
              </span>
            ))}
          </div>
        ) : noSources ? (
          <span className="text-[10px] text-muted-foreground/50 ml-auto italic">
            description only
          </span>
        ) : null}
      </div>
    </button>
  )
}

// ---------------------------------------------------------------------------
// Generate Ticket Picker (separate from search)
// ---------------------------------------------------------------------------

/** Normalised ticket used throughout the picker & generate flow. */
interface PickerTicket {
  id: string
  identifier: string
  title: string
  state: string | null
  assignee: string | null
  /** Which provider this ticket came from */
  source: 'linear' | 'jira'
}

function GenerateTicketPicker({
  open,
  onClose,
  onSelect,
}: {
  open: boolean
  onClose: () => void
  onSelect: (ticket: PickerTicket) => void
}) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<PickerTicket[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [endCursor, setEndCursor] = useState<string | null>(null)
  const [hasNextPage, setHasNextPage] = useState(false)
  const [pendingTicket, setPendingTicket] = useState<PickerTicket | null>(null)
  const [provider, setProvider] = useState<'linear' | 'jira' | null>(null)
  const [providerDetected, setProviderDetected] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<NodeJS.Timeout | null>(null)
  const observerRef = useRef<IntersectionObserver | null>(null)

  // Detect which ticket provider is connected (once on open)
  useEffect(() => {
    if (!open) return
    let cancelled = false
    setProvider(null)
    setProviderDetected(false)
    setPendingTicket(null)
    setQuery('')
    setResults([])
    getIntegrationStatus().then((s) => {
      if (cancelled) return
      setProvider(detectTicketProvider(s))
      setProviderDetected(true)
    }).catch(() => {
      if (cancelled) return
      setProvider(null)
      setProviderDetected(true)
    })
    return () => { cancelled = true }
  }, [open])

  const loadTickets = useCallback(async (p: 'linear' | 'jira', q?: string, cursor?: string) => {
    if (cursor) {
      setLoadingMore(true)
    } else {
      setLoading(true)
    }
    try {
      if (p === 'jira') {
        // Jira — no cursor pagination, single page
        const jiraResult = await searchJiraIssues(q)
        const tickets: PickerTicket[] = jiraResult.issues.map((j) => ({
          id: j.jira_id,
          identifier: j.key,
          title: j.summary,
          state: j.status,
          assignee: j.assignee,
          source: 'jira',
        }))
        setResults(tickets)
        setHasNextPage(false)
        setEndCursor(null)
      } else {
        // Linear — cursor-based pagination
        const linearResult = await searchLinearTickets(q, 20, cursor)
        const tickets: PickerTicket[] = linearResult.tickets.map((t) => ({
          id: t.id,
          identifier: t.identifier,
          title: t.title,
          state: t.state,
          assignee: t.assignee,
          source: 'linear',
        }))
        if (cursor) {
          setResults((prev) => [...prev, ...tickets])
        } else {
          setResults(tickets)
        }
        setHasNextPage(linearResult.has_next_page)
        setEndCursor(linearResult.end_cursor)
      }
    } catch {
      if (!cursor) setResults([])
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }, [])

  // Load tickets when provider is determined or query changes (debounced)
  useEffect(() => {
    if (!open || !provider) return
    setHasNextPage(false)
    setEndCursor(null)
    if (searchRef.current) clearTimeout(searchRef.current)
    // Load immediately when provider first set (query is empty), debounce on query changes
    const delay = query.trim() ? 300 : 0
    searchRef.current = setTimeout(() => {
      loadTickets(provider, query.trim() || undefined)
    }, delay)
    return () => {
      if (searchRef.current) clearTimeout(searchRef.current)
    }
  }, [query, open, provider, loadTickets])

  // Infinite scroll — ref callback attaches observer when sentinel mounts
  const loadingMoreRef = useRef(loadingMore)
  const endCursorRef = useRef(endCursor)
  const queryRef = useRef(query)
  const providerRef = useRef(provider)
  loadingMoreRef.current = loadingMore
  endCursorRef.current = endCursor
  queryRef.current = query
  providerRef.current = provider

  const sentinelRef = useCallback(
    (node: HTMLDivElement | null) => {
      if (observerRef.current) {
        observerRef.current.disconnect()
        observerRef.current = null
      }
      if (!node) return
      observerRef.current = new IntersectionObserver(
        (entries) => {
          if (entries[0]?.isIntersecting && !loadingMoreRef.current && providerRef.current) {
            loadTickets(providerRef.current, queryRef.current.trim() || undefined, endCursorRef.current ?? undefined)
          }
        },
        { threshold: 0 }
      )
      observerRef.current.observe(node)
    },
    [loadTickets]
  )

  // Close on click outside
  useEffect(() => {
    if (!open) return
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      ref={containerRef}
      className="absolute top-full right-0 mt-2 w-80 z-50 rounded-xl border border-border bg-elevated shadow-lg overflow-hidden animate-scale-in"
    >
      {pendingTicket ? (
        /* Confirmation */
        <div className="p-4 space-y-3">
          <p className="section-label">Generate context for</p>
          <div className="flex items-start gap-3">
            <span className="shrink-0 font-mono text-xs font-medium text-primary mt-0.5">
              {pendingTicket.identifier}
            </span>
            <p className="text-sm text-foreground">{pendingTicket.title}</p>
          </div>
          <div className="flex items-center gap-2 pt-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setPendingTicket(null)}
            >
              Back
            </Button>
            <Button
              size="sm"
              onClick={() => onSelect(pendingTicket)}
            >
              <Zap className="h-3 w-3 mr-1" />
              Generate
            </Button>
          </div>
        </div>
      ) : providerDetected && !provider ? (
        <div className="flex flex-col items-center gap-2 py-8 px-4 text-center">
          <p className="text-sm font-medium text-foreground">No ticket provider connected</p>
          <p className="text-xs text-muted-foreground">
            Connect Linear or Jira in Settings to generate context pages.
          </p>
        </div>
      ) : (
        <>
          <div className="p-3 border-b border-border space-y-2">
            {provider && (
              <div className="flex items-center gap-1.5">
                <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium ${
                  provider === 'jira'
                    ? 'bg-blue-500/10 text-blue-500'
                    : 'bg-violet-400/10 text-violet-400'
                }`}>
                  {provider === 'jira' ? 'Jira' : 'Linear'}
                </span>
              </div>
            )}
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                placeholder={provider === 'jira' ? 'Search Jira issues...' : 'Search Linear tickets...'}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="pl-8 h-8 text-sm"
                autoFocus
              />
            </div>
          </div>
          <div className="max-h-64 overflow-y-auto">
            {loading || !provider ? (
              <div className="p-3 space-y-2">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <Skeleton className="h-4 w-14 shrink-0" />
                    <Skeleton className="h-4 w-full" />
                  </div>
                ))}
              </div>
            ) : results.length > 0 ? (
              <>
                <div className="px-3 py-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                  {query.trim() ? 'Results' : 'Your tickets'}
                </div>
                {results.map((ticket) => (
                  <button
                    key={ticket.id}
                    onClick={() => setPendingTicket(ticket)}
                    className="flex w-full items-start gap-3 px-3 py-2.5 text-left transition-colors hover:bg-muted/50"
                  >
                    <span className="shrink-0 font-mono text-xs font-medium text-primary mt-0.5">
                      {ticket.identifier}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-foreground truncate">{ticket.title}</p>
                      <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
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
                {hasNextPage && (
                  <div ref={sentinelRef} className="px-3 py-2 text-xs text-center text-muted-foreground">
                    {loadingMore ? 'Loading...' : ''}
                  </div>
                )}
              </>
            ) : (
              <p className="px-3 py-6 text-center text-sm text-muted-foreground">
                {query.trim() ? 'No tickets found' : 'No assigned tickets'}
              </p>
            )}
          </div>
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Context Feed Page
// ---------------------------------------------------------------------------

export default function ContextFeedPage() {
  const router = useRouter()

  const [pages, setPages] = useState<ContextPageRow[]>([])
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [generateOpen, setGenerateOpen] = useState(false)

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

  // Handle generate selection
  const handleGenerateSelect = useCallback(
    (ticket: PickerTicket) => {
      setGenerateOpen(false)
      const params = new URLSearchParams({ ticket: ticket.identifier })
      if (ticket.source === 'linear') {
        params.set('linear_issue_id', ticket.id)
      } else if (ticket.source === 'jira') {
        params.set('jira_issue_id', ticket.id)
      }
      router.push(`/dashboard/context/generate?${params.toString()}`)
    },
    [router]
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

  const hasActiveFilters = statusFilter !== 'all' || debouncedQuery.trim().length > 0

  const clearFilters = useCallback(() => {
    setStatusFilter('all')
    setSearchQuery('')
  }, [])

  // Stats
  const stats = useMemo(() => {
    const ready = pages.filter((p) => p.status === 'ready').length
    const total = pages.length
    const totalSources = pages.reduce((sum, p) => sum + (p.sources?.length ?? 0), 0)
    return { ready, total, totalSources }
  }, [pages])

  // -----------------------------------------------------------------------
  // Loading skeleton
  // -----------------------------------------------------------------------
  if (isLoading) {
    return (
      <div className="space-y-6 animate-fade-in-up">
        <div className="flex items-center justify-between">
          <Skeleton className="h-3 w-28" />
          <Skeleton className="h-8 w-32" />
        </div>
        <div className="flex gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-4 w-16" />
          ))}
        </div>
        <Skeleton className="h-9 w-full max-w-xs" />
        <div className="rounded-xl border border-border overflow-hidden divide-y divide-border">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="px-4 py-3.5 space-y-2">
              <div className="flex items-center justify-between">
                <Skeleton className="h-4 w-52" />
                <Skeleton className="h-1.5 w-1.5 rounded-full" />
              </div>
              <div className="flex items-center gap-3">
                <Skeleton className="h-3 w-16" />
                <Skeleton className="h-3 w-12" />
                <div className="flex gap-1 ml-auto">
                  <Skeleton className="h-4 w-12 rounded-full" />
                  <Skeleton className="h-4 w-10 rounded-full" />
                </div>
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
        <h3 className="section-label">Context Feed</h3>
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
    <div className="space-y-5 animate-fade-in-up">
      {/* Header row — title + generate button */}
      <div className="flex items-center justify-between relative">
        <div>
          <h3 className="section-label">Context Feed</h3>
          {stats.total > 0 && (
            <p className="text-xs text-muted-foreground mt-1">
              {stats.ready} of {stats.total} ready · {stats.totalSources} sources linked
            </p>
          )}
        </div>
        <div className="relative">
          <Button
            size="sm"
            onClick={() => setGenerateOpen(!generateOpen)}
            className="gap-1.5"
          >
            <Plus className="h-3.5 w-3.5" />
            Generate
          </Button>
          <GenerateTicketPicker
            open={generateOpen}
            onClose={() => setGenerateOpen(false)}
            onSelect={handleGenerateSelect}
          />
        </div>
      </div>

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

      {/* Search — purely for filtering the feed */}
      <div className="max-w-xs">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Filter by title or ticket ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {/* Feed list */}
      {filteredPages.length > 0 ? (
        <div className="rounded-xl border bg-card overflow-hidden divide-y divide-border stagger-children">
          {filteredPages.map((page) => (
            <FeedRow
              key={page.id}
              page={page}
              onClick={() => router.push(`/dashboard/context/${page.id}`)}
            />
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
        <div className="rounded-xl border bg-card overflow-hidden">
          <div className="flex flex-col items-center gap-3 py-16 px-4 text-center">
            <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center mb-2">
              <Zap className="h-5 w-5 text-primary" />
            </div>
            <p className="text-sm font-medium text-foreground">
              No context pages yet
            </p>
            <p className="text-xs text-muted-foreground max-w-[280px]">
              Generate context for a ticket to aggregate all related discussions, code, and decisions into one place.
            </p>
            <Button
              className="mt-2 gap-1.5"
              onClick={() => setGenerateOpen(true)}
            >
              <Plus className="h-3.5 w-3.5" />
              Generate Context
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
