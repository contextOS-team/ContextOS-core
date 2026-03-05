'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  generateContextPage,
  getContextPage,
  searchLinearTickets,
  type LinearTicketSearchResult,
} from '@/lib/api'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface StepContextProps {
  onComplete: () => void
}

type StepState = 'intro' | 'picking' | 'generating' | 'ready' | 'error'

const PROGRESS_MESSAGES = [
  'Pulling your tickets...',
  'Analyzing context...',
  'Gathering related discussions...',
  'Generating prompt...',
]

const PRIORITY_LABELS: Record<number, string> = {
  0: 'None',
  1: 'Urgent',
  2: 'High',
  3: 'Normal',
  4: 'Low',
}

export function StepContext({ onComplete }: StepContextProps) {
  const [state, setState] = useState<StepState>('intro')
  const [messageIndex, setMessageIndex] = useState(0)
  const [contextData, setContextData] = useState<{
    ticketId: string
    title: string
    context: string
    prompt: string
  } | null>(null)

  // Ticket picker state
  const [tickets, setTickets] = useState<LinearTicketSearchResult[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [loadingTickets, setLoadingTickets] = useState(false)
  const [selectedTicket, setSelectedTicket] = useState<LinearTicketSearchResult | null>(null)
  const debounceRef = useRef<NodeJS.Timeout | null>(null)

  // Rotate progress messages
  useEffect(() => {
    if (state !== 'generating') return
    const interval = setInterval(() => {
      setMessageIndex((prev) => (prev + 1) % PROGRESS_MESSAGES.length)
    }, 3000)
    return () => clearInterval(interval)
  }, [state])

  // Load assigned tickets when entering picker
  const loadTickets = useCallback(async (query?: string) => {
    setLoadingTickets(true)
    try {
      const result = await searchLinearTickets(query, 10)
      setTickets(result.tickets)
    } catch {
      setTickets([])
    } finally {
      setLoadingTickets(false)
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
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      loadTickets(searchQuery || undefined)
    }, 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [searchQuery, state, loadTickets])

  const generateForTicket = useCallback(async (ticket: LinearTicketSearchResult) => {
    setSelectedTicket(ticket)
    setState('generating')

    try {
      // Trigger context page generation (pass linear_issue_id so backend syncs ticket first if needed)
      try {
        await generateContextPage(ticket.identifier, ticket.id)
      } catch {
        // Trigger may fail — backend handles this in background
      }

      // Poll for the generated page (up to 20s)
      for (let i = 0; i < 20; i++) {
        await new Promise((r) => setTimeout(r, 1000))
        try {
          const page = await getContextPage(ticket.identifier)
          if (page && page.status === 'ready' && page.content) {
            setContextData({
              ticketId: page.ticket_identifier,
              title: page.title,
              context: page.summary || page.content.slice(0, 500),
              prompt: page.content,
            })
            setState('ready')
            return
          }
        } catch {
          // Not ready yet
        }
      }

      setState('error')
    } catch {
      setState('error')
    }
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
            tickets.map((ticket) => (
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
            ))
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

  // Generating state
  if (state === 'generating') {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold text-foreground">
            Generating context
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

        {/* Shimmer skeleton */}
        <div className="space-y-4 rounded-lg border border-border bg-background p-5">
          <div className="flex items-center gap-3">
            <Skeleton className="h-5 w-16" />
            <Skeleton className="h-5 w-48" />
          </div>
          <div className="space-y-2">
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-[90%]" />
            <Skeleton className="h-3 w-[75%]" />
          </div>
          <div className="space-y-2">
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-[85%]" />
            <Skeleton className="h-3 w-[60%]" />
          </div>
          <div className="rounded-md border border-border bg-muted/30 p-4 space-y-2">
            <Skeleton className="h-3 w-[70%]" />
            <Skeleton className="h-3 w-[50%]" />
            <Skeleton className="h-3 w-[80%]" />
            <Skeleton className="h-3 w-[40%]" />
          </div>
        </div>

        <p className="text-center text-sm font-mono text-muted-foreground">
          {PROGRESS_MESSAGES[messageIndex]}
        </p>
      </div>
    )
  }

  // Error state
  if (state === 'error') {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold text-foreground">
            Couldn&apos;t generate context
          </h2>
          <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
            Generation is taking longer than expected. You can try a different
            ticket or generate context pages from the dashboard later.
          </p>
        </div>

        <div className="space-y-3">
          <Button onClick={enterPicker} variant="outline" className="w-full">
            Try another ticket
          </Button>
          <Button onClick={onComplete} className="w-full">
            Continue to dashboard
          </Button>
        </div>
      </div>
    )
  }

  // Ready state — show generated context page
  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold text-foreground">
          Your first context page
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Here&apos;s what ContextOS delivers for every ticket
        </p>
      </div>

      {contextData && (
        <div className="space-y-4 rounded-lg border border-border bg-background p-5 animate-fade-in-up">
          <div className="flex items-start gap-2">
            <span className="shrink-0 font-mono text-sm font-medium text-primary">
              {contextData.ticketId}
            </span>
            <span className="text-sm font-medium text-foreground">
              {contextData.title}
            </span>
          </div>

          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Context
            </h3>
            <div className="space-y-2 text-sm leading-relaxed text-foreground/80">
              {contextData.context.split('\n\n').map((paragraph, i) => (
                <p key={i}>{paragraph}</p>
              ))}
            </div>
          </div>

          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Prompt
            </h3>
            <div className="rounded-md border border-border bg-muted/30 p-4">
              <pre className="whitespace-pre-wrap text-xs font-mono leading-relaxed text-foreground/70">
                {contextData.prompt}
              </pre>
            </div>
          </div>
        </div>
      )}

      <Button onClick={onComplete} className="w-full">
        Continue
      </Button>
    </div>
  )
}
