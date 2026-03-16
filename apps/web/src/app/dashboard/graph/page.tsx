'use client'

import { useState, useCallback, useEffect } from 'react'
import dynamic from 'next/dynamic'
import { Search, Layers } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'

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

const STORAGE_KEY = 'contextos-recent-graph-tickets'
const MAX_RECENT = 5

function getRecentTickets(): string[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as string[]) : []
  } catch {
    return []
  }
}

function saveRecentTicket(ticketId: string) {
  try {
    const current = getRecentTickets()
    const updated = [ticketId, ...current.filter((id) => id !== ticketId)].slice(
      0,
      MAX_RECENT
    )
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
  } catch {
    // Ignore localStorage errors
  }
}

export default function GraphPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [activeTicketId, setActiveTicketId] = useState<string | null>(null)
  const [recentTickets, setRecentTickets] = useState<string[]>([])

  useEffect(() => {
    setRecentTickets(getRecentTickets())
  }, [])

  const handleSearch = useCallback(() => {
    const trimmed = searchQuery.trim()
    if (!trimmed) return
    setActiveTicketId(trimmed)
    saveRecentTicket(trimmed)
    setRecentTickets(getRecentTickets())
  }, [searchQuery])

  const handleSelectRecent = useCallback((id: string) => {
    setActiveTicketId(id)
    setSearchQuery(id)
    saveRecentTicket(id)
    setRecentTickets(getRecentTickets())
  }, [])

  return (
    <div className="animate-fade-in-up">
      <h1 className="text-xl font-semibold text-foreground">Graph Explorer</h1>
      <p className="text-sm text-muted-foreground mt-1">
        Explore the knowledge graph around any ticket
      </p>

      {/* Search bar */}
      <div className="relative mt-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search by ticket ID (e.g., ENG-123)..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          className="w-full rounded-lg border bg-card pl-10 pr-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
          autoFocus
        />
      </div>

      {/* Recent tickets chips */}
      {!activeTicketId && recentTickets.length > 0 && (
        <div className="flex items-center gap-2 mt-4">
          <span className="section-label">Recent</span>
          {recentTickets.map((id) => (
            <button
              key={id}
              onClick={() => handleSelectRecent(id)}
              className="rounded-full border px-3 py-1 text-xs font-mono text-muted-foreground hover:text-foreground hover:border-primary/50 transition-colors"
            >
              {id}
            </button>
          ))}
        </div>
      )}

      {/* Graph area */}
      {activeTicketId ? (
        <div className="mt-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setActiveTicketId(null)}
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Back to search
              </button>
              <span className="font-mono text-sm text-foreground">
                {activeTicketId}
              </span>
            </div>
          </div>
          <div className="h-[calc(100vh-280px)] rounded-xl border border-border overflow-hidden">
            <GraphExplorer
              ticketIdentifier={activeTicketId}
              className="h-full w-full"
            />
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-center h-96 mt-6 rounded-xl border border-dashed border-border">
          <div className="text-center">
            <Layers className="h-10 w-10 mx-auto text-muted-foreground/30" />
            <p className="text-sm text-muted-foreground mt-3">
              Enter a ticket ID to explore its knowledge graph
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
