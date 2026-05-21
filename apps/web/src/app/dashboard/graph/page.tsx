'use client'

import { useState, useCallback, useEffect } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import dynamic from 'next/dynamic'
import { Search } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { LensSelector } from '@/components/graph/lens-selector'
import type { GraphLens } from '@/components/graph/types'
import { getIntegrationStatus } from '@/lib/api'

const GraphExplorer = dynamic(
  () =>
    import('@/components/graph/graph-explorer').then((m) => ({
      default: m.GraphExplorer,
    })),
  {
    ssr: false,
    loading: () => <GraphTabSkeleton />,
  }
)

function GraphTabSkeleton() {
  return (
    <div className="flex items-center justify-center h-full w-full">
      <div className="relative h-48 w-64">
        <Skeleton className="absolute left-1/2 top-8 h-6 w-6 -translate-x-1/2 rounded-full" />
        <Skeleton className="absolute left-8 top-24 h-4 w-4 rounded-full" />
        <Skeleton className="absolute right-8 top-20 h-4 w-4 rounded-full" />
        <Skeleton className="absolute left-16 bottom-4 h-3 w-3 rounded-full" />
        <Skeleton className="absolute right-16 bottom-8 h-3 w-3 rounded-full" />
      </div>
    </div>
  )
}

const LENS_SUBTITLES: Record<GraphLens, string> = {
  my_work: 'Your assigned tickets and their connections',
  sprint: 'Active sprint tickets and context',
  blocked: 'Blocked tickets and dependencies',
  browse: 'Your workspace connections',
}

export default function GraphPage() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const focusParam = searchParams.get('focus')
  const VALID_LENSES = new Set<GraphLens>(['my_work', 'sprint', 'blocked', 'browse'])
  const rawLens = searchParams.get('lens')
  const lensParam: GraphLens = rawLens && VALID_LENSES.has(rawLens as GraphLens) ? (rawLens as GraphLens) : 'my_work'

  const [lens, setLens] = useState<GraphLens>(focusParam ? 'browse' : lensParam)
  const [searchQuery, setSearchQuery] = useState(focusParam ?? '')
  const [focusTicket, setFocusTicket] = useState<string | null>(focusParam)
  const [graphKey, setGraphKey] = useState(0)
  const [sprintUnavailable, setSprintUnavailable] = useState<string | undefined>()

  // Check provider for sprint availability
  useEffect(() => {
    getIntegrationStatus()
      .then((status) => {
        const hasLinear = status.linear?.status === 'connected'
        const hasJira = status.jira?.status === 'connected'
        if (hasJira && !hasLinear) {
          setSprintUnavailable('Sprint view is available for Linear workspaces')
        }
      })
      .catch((err) => console.error('Failed to check integration status:', err))
  }, [])

  // Sync URL param changes
  useEffect(() => {
    if (focusParam !== focusTicket) {
      setFocusTicket(focusParam)
      setSearchQuery(focusParam ?? '')
      if (focusParam) setLens('browse')
      setGraphKey((k) => k + 1)
    }
  }, [focusParam]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleLensChange = useCallback(
    (newLens: GraphLens) => {
      setLens(newLens)
      if (newLens !== 'browse') {
        setFocusTicket(null)
        setSearchQuery('')
      }
      const params = new URLSearchParams()
      params.set('lens', newLens)
      router.push(`/dashboard/graph?${params.toString()}`)
      setGraphKey((k) => k + 1)
    },
    [router]
  )

  const handleSearch = useCallback(() => {
    const trimmed = searchQuery.trim()
    if (!trimmed) {
      setFocusTicket(null)
      router.push(`/dashboard/graph?lens=${lens}`)
      setGraphKey((k) => k + 1)
      return
    }
    setFocusTicket(trimmed)
    setLens('browse')
    router.push(`/dashboard/graph?lens=browse&focus=${encodeURIComponent(trimmed)}`)
    setGraphKey((k) => k + 1)
  }, [searchQuery, router, lens])

  const handleClearFocus = useCallback(() => {
    setFocusTicket(null)
    setSearchQuery('')
    router.push(`/dashboard/graph?lens=${lens}`)
    setGraphKey((k) => k + 1)
  }, [router, lens])

  const subtitle = focusTicket
    ? `Showing neighborhood of ${focusTicket}`
    : LENS_SUBTITLES[lens]

  return (
    <div className="animate-fade-in-up flex flex-col h-[calc(100vh-80px)]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Knowledge Graph</h1>
          <p className="text-sm text-muted-foreground mt-1">{subtitle}</p>
        </div>

        {/* Search — focuses within the graph */}
        <div className="relative w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Focus on ticket (e.g., ENG-123)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="dashboard-input w-full rounded-lg border pl-10 pr-4 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/35"
          />
        </div>
      </div>

      {/* Lens selector */}
      <div className="flex items-center gap-3 mt-3">
        <LensSelector
          activeLens={lens}
          onLensChange={handleLensChange}
          sprintDisabled={!!sprintUnavailable}
          sprintTooltip={sprintUnavailable}
        />

        {/* Focus indicator */}
        {focusTicket && (
          <>
            <div className="h-4 w-px bg-border" />
            <span className="text-xs text-muted-foreground">Focused on</span>
            <span className="font-mono text-xs text-foreground bg-card border rounded-md px-2 py-0.5">
              {focusTicket}
            </span>
            <button
              onClick={handleClearFocus}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              Show all
            </button>
          </>
        )}
      </div>

      {/* Graph canvas — takes remaining height */}
      <div className="dashboard-panel flex-1 mt-3 overflow-hidden min-h-0 relative">
        <GraphExplorer
          key={graphKey}
          lens={lens}
          ticketIdentifier={focusTicket ?? undefined}
          className="h-full w-full"
        />
      </div>
    </div>
  )
}
