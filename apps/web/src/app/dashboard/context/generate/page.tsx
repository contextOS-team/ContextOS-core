'use client'

import { Suspense, useState, useEffect, useCallback, useRef } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { apiFetchSSE, SOURCE_LABELS } from '@/lib/api'
import { GenerationProgress } from '@/components/generation-progress'
import type { GenerationState } from '@/lib/context-feed'

function GeneratePageContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const ticket = searchParams.get('ticket')
  const linearIssueId = searchParams.get('linear_issue_id')

  const [generation, setGeneration] = useState<GenerationState | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const startGeneration = useCallback(
    (ticketIdentifier: string, issueId?: string | null) => {
      abortRef.current?.abort()

      setGeneration({
        ticket: ticketIdentifier,
        steps: [],
        status: 'streaming',
      })

      const streamPath = issueId
        ? `/api/context/${encodeURIComponent(ticketIdentifier)}/generate-stream?linear_issue_id=${encodeURIComponent(issueId)}`
        : `/api/context/${encodeURIComponent(ticketIdentifier)}/generate-stream`

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
                      ? {
                          ...s,
                          status: 'complete' as const,
                          count: event.count,
                          detail: event.detail,
                        }
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
            prev
              ? { ...prev, status: 'error', errorMessage: error.message }
              : prev
          )
        }
      )

      abortRef.current = controller
    },
    []
  )

  // Auto-start generation on mount
  useEffect(() => {
    if (!ticket) {
      router.replace('/dashboard/context')
      return
    }

    startGeneration(ticket, linearIssueId)

    return () => {
      abortRef.current?.abort()
    }
    // Only run on mount — ticket/linearIssueId come from URL and don't change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // On completion, redirect to detail page
  useEffect(() => {
    if (generation?.status === 'complete' && generation.contextPageId) {
      const timer = setTimeout(() => {
        router.replace(`/dashboard/context/${generation.contextPageId}`)
      }, 1200)
      return () => clearTimeout(timer)
    }
  }, [generation?.status, generation?.contextPageId, router])

  if (!ticket) return null

  return (
    <div className="space-y-6 animate-fade-in-up">
      <Link
        href="/dashboard/context"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Context
      </Link>

      <div className="max-w-lg mx-auto mt-12">
        {generation && (
          <GenerationProgress
            ticketIdentifier={generation.ticket}
            steps={generation.steps}
            status={generation.status}
            errorMessage={generation.errorMessage}
            onRetry={() => startGeneration(ticket, linearIssueId)}
            onDismiss={() => {
              abortRef.current?.abort()
              router.push('/dashboard/context')
            }}
          />
        )}

        {generation?.status === 'error' && (
          <div className="mt-4 text-center">
            <Button
              variant="ghost"
              onClick={() => router.push('/dashboard/context')}
            >
              Back to Feed
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}

export default function GeneratePage() {
  return (
    <Suspense>
      <GeneratePageContent />
    </Suspense>
  )
}
