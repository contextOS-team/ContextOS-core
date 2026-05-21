'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { Skeleton } from '@/components/ui/skeleton'
import { fetchWorkspaceGraph } from '@/lib/api'
import { formatRelativeTime } from '@/lib/utils'
import { toDecisionView, type DecisionNodeView } from '../decision-node'

export default function DecisionDetailPage() {
  const params = useParams<{ id: string }>()
  const decisionId = useMemo(() => decodeURIComponent(params.id), [params.id])
  const [decision, setDecision] = useState<DecisionNodeView | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const graph = await fetchWorkspaceGraph(300)
        if (cancelled) return

        const node = graph.nodes.find((item) => item.id === decisionId && item.entity_type === 'Decision')
        setDecision(node ? toDecisionView(node) : null)
        setError(null)
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load decision')
        }
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    void load()

    return () => {
      cancelled = true
    }
  }, [decisionId])

  if (isLoading) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-40 w-full rounded-xl" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-4">
        <Link href="/dashboard/decisions" className="text-sm text-muted-foreground hover:text-foreground">
          &larr; Decisions
        </Link>
        <p className="text-sm text-destructive">Failed to load decision: {error}</p>
      </div>
    )
  }

  if (!decision) {
    return (
      <div className="space-y-4">
        <Link href="/dashboard/decisions" className="text-sm text-muted-foreground hover:text-foreground">
          &larr; Decisions
        </Link>
        <p className="text-sm text-muted-foreground">Decision not found.</p>
      </div>
    )
  }

  return (
    <article className="max-w-3xl space-y-6 animate-fade-in-up">
      <Link href="/dashboard/decisions" className="text-sm text-muted-foreground hover:text-foreground">
        &larr; Decisions
      </Link>

      <header className="space-y-3">
        <h1 className="text-2xl font-semibold leading-tight tracking-[-0.03em] text-foreground">
          {decision.title}
        </h1>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          {decision.authorName && <span>{decision.authorName}</span>}
          {decision.sourceChannel && <span className="font-mono">{decision.sourceChannel}</span>}
          {decision.date && <span>{formatRelativeTime(decision.date)}</span>}
          {decision.confidence !== null && (
            <span className="tabular-nums">{Math.round(decision.confidence * 100)}% confidence</span>
          )}
        </div>
      </header>

      {decision.sourceQuote && (
        <blockquote className="rounded-xl bg-card px-5 py-4 text-base italic leading-relaxed text-foreground">
          &ldquo;{decision.sourceQuote}&rdquo;
        </blockquote>
      )}

      {decision.rationale && (
        <section className="space-y-2">
          <h2 className="text-sm font-medium text-foreground">Rationale</h2>
          <p className="text-sm leading-relaxed text-muted-foreground">
            {decision.rationale}
          </p>
        </section>
      )}

      {decision.participants.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-medium text-foreground">People</h2>
          <div className="flex flex-wrap gap-2">
            {decision.participants.map((name) => (
              <span key={name} className="rounded-full bg-card px-2 py-1 text-xs text-muted-foreground">
                {name}
              </span>
            ))}
          </div>
        </section>
      )}
    </article>
  )
}
