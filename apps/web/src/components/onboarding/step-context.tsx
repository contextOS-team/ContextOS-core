'use client'

import { useEffect, useState, useRef } from 'react'
import { createClient } from '@/lib/supabase/client'
import {
  getIntegrationStatus,
  generateContextPage,
  getContextPage,
  type ContextPageResponse,
} from '@/lib/api'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'

interface StepContextProps {
  onComplete: () => void
}

type StepState = 'generating' | 'ready' | 'completing'

const PROGRESS_MESSAGES = [
  'Pulling your tickets...',
  'Analyzing context...',
  'Gathering related discussions...',
  'Generating prompt...',
]

const MOCK_DATA = {
  ticketId: 'ENG-42',
  title: 'Implement user notification preferences',
  context:
    'This ticket covers adding a notification preferences panel to user settings. The feature was discussed in the #eng-notifications Slack channel where the team agreed on supporting email, in-app, and Slack notification channels. The PM outlined requirements in the Notion spec document, emphasizing per-event granularity.\n\nRelated PRs include the notification service refactor (PR #187) and the user settings page redesign (PR #201). The database schema already has a notification_preferences JSONB column on the users table from a previous migration.',
  prompt:
    '## Context for ENG-42: Implement user notification preferences\n\nYou are implementing a notification preferences UI. The user should be able to toggle notifications per event type (assigned, mentioned, status-change) across three channels (email, in-app, Slack).\n\nExisting schema: `users.notification_preferences` (JSONB)\nAPI endpoint: `PATCH /api/users/me/preferences`\nDesign reference: Notion spec linked in ticket\n\nKey constraints:\n- Default all notifications to ON for new users\n- Slack channel requires active Slack integration\n- Changes save optimistically with rollback on failure',
}

export function StepContext({ onComplete }: StepContextProps) {
  const [state, setState] = useState<StepState>('generating')
  const [messageIndex, setMessageIndex] = useState(0)
  const [contextData, setContextData] = useState<{
    ticketId: string
    title: string
    context: string
    prompt: string
  } | null>(null)
  const attemptedRef = useRef(false)

  // Rotate progress messages
  useEffect(() => {
    if (state !== 'generating') return
    const interval = setInterval(() => {
      setMessageIndex((prev) => (prev + 1) % PROGRESS_MESSAGES.length)
    }, 3000)
    return () => clearInterval(interval)
  }, [state])

  // Attempt real generation on mount
  useEffect(() => {
    if (attemptedRef.current) return
    attemptedRef.current = true

    async function attemptGeneration() {
      try {
        // Check if Linear is connected
        const status = await getIntegrationStatus()
        if (status.linear.status !== 'connected') {
          // No Linear -- use mock
          await simulateDelay()
          useMockData()
          return
        }

        // Try to find an assigned ticket from existing context pages
        const supabase = createClient()
        const { data: pages } = await supabase
          .from('context_pages')
          .select('ticket_identifier, title')
          .is('deleted_at', null)
          .order('updated_at', { ascending: false })
          .limit(1)

        if (!pages || pages.length === 0) {
          // No tickets available -- use mock
          await simulateDelay()
          useMockData()
          return
        }

        const ticket = pages[0]

        // Attempt generation
        try {
          await generateContextPage(ticket.ticket_identifier)
        } catch {
          // Generation trigger failed -- try fetching existing page
        }

        // Wait briefly then fetch the page
        await new Promise((r) => setTimeout(r, 2000))

        try {
          const page = await getContextPage(ticket.ticket_identifier)
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
          // Fetch failed -- fall through to mock
        }

        // Fallback to mock
        await simulateDelay()
        useMockData()
      } catch {
        // Any error -- gracefully fall back to mock
        await simulateDelay()
        useMockData()
      }
    }

    attemptGeneration()
  }, [])

  function simulateDelay() {
    return new Promise((r) => setTimeout(r, 2500))
  }

  function useMockData() {
    setContextData(MOCK_DATA)
    setState('ready')
  }

  if (state === 'generating') {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold text-foreground">
            Your first context page
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            See what ContextOS generates for your tickets
          </p>
        </div>

        {/* Shimmer skeleton matching context page layout */}
        <div className="space-y-4 rounded-lg border border-border bg-background p-5">
          {/* Title bar skeleton */}
          <div className="flex items-center gap-3">
            <Skeleton className="h-5 w-16" />
            <Skeleton className="h-5 w-48" />
          </div>

          {/* Paragraph skeletons */}
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

          {/* Code block skeleton */}
          <div className="rounded-md border border-border bg-muted/30 p-4 space-y-2">
            <Skeleton className="h-3 w-[70%]" />
            <Skeleton className="h-3 w-[50%]" />
            <Skeleton className="h-3 w-[80%]" />
            <Skeleton className="h-3 w-[40%]" />
          </div>
        </div>

        {/* Rotating progress message */}
        <p className="text-center text-sm font-mono text-muted-foreground">
          {PROGRESS_MESSAGES[messageIndex]}
        </p>
      </div>
    )
  }

  if (state === 'completing') {
    return (
      <div className="space-y-6 py-4 text-center">
        <div>
          <h2 className="text-2xl font-bold text-foreground">
            You&apos;re all set!
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Context pages will generate automatically as tickets are assigned.
          </p>
        </div>
        <Button onClick={onComplete} className="w-full">
          Go to Dashboard
        </Button>
      </div>
    )
  }

  // Ready state -- show context page content
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
          {/* Ticket identifier + title */}
          <div className="flex items-start gap-2">
            <span className="shrink-0 font-mono text-sm font-medium text-primary">
              {contextData.ticketId}
            </span>
            <span className="text-sm font-medium text-foreground">
              {contextData.title}
            </span>
          </div>

          {/* Context section */}
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

          {/* Prompt section */}
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

      <Button onClick={() => setState('completing')} className="w-full">
        Continue
      </Button>
    </div>
  )
}
