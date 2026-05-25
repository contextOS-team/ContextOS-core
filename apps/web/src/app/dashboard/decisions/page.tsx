'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Skeleton } from '@/components/ui/skeleton'
import { fetchDecisions } from '@/lib/api'
import { formatRelativeTime } from '@/lib/utils'
import { sortDecisions, toDecisionView, type DecisionNodeView } from './decision-node'

export default function DecisionsPage() {
  const [decisions, setDecisions] = useState<DecisionNodeView[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const nodes = await fetchDecisions()
        if (cancelled) return

        setDecisions(
          nodes
            .filter((node) => node.entity_type === 'Decision')
            .map(toDecisionView)
            .sort(sortDecisions)
        )
        setError(null)
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load decisions')
        }
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    void load()

    return () => {
      cancelled = true
    }
  }, [])

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl space-y-5">
        <Skeleton className="h-7 w-40" />
        <Skeleton className="h-20 w-full rounded-xl" />
        <Skeleton className="h-20 w-full rounded-xl" />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 animate-fade-in-up">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Decisions</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {decisions.length} decision{decisions.length === 1 ? '' : 's'} from connected sources
          </p>
        </div>
        <Link href="/dashboard" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
          Home
        </Link>
      </div>

      {error && (
        <p className="text-sm text-destructive">
          Failed to load decisions: {error}
        </p>
      )}

      {!error && decisions.length === 0 && (
        <p className="rounded-xl bg-card px-4 py-4 text-sm text-muted-foreground">
          No decisions found yet.
        </p>
      )}

      <div className="divide-y divide-border overflow-hidden rounded-lg border border-border bg-card/80">
        {decisions.map((decision) => (
          <Link
            key={decision.id}
            href={`/dashboard/decisions/${encodeURIComponent(decision.id)}`}
            className="block px-5 py-4 transition-colors duration-150 hover:bg-elevated/70"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <h2 className="truncate text-[15px] font-medium text-foreground">
                  {decision.title}
                </h2>
                <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  {decision.authorName && <span>{decision.authorName}</span>}
                  {decision.sourceChannel && (
                    <span className="font-mono">{decision.sourceChannel}</span>
                  )}
                  {decision.date && <span>{formatRelativeTime(decision.date)}</span>}
                </div>
              </div>
              {decision.confidence !== null && (
                <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                  {Math.round(decision.confidence * 100)}%
                </span>
              )}
            </div>
            {decision.sourceQuote && (
              <p className="mt-3 line-clamp-2 text-sm italic leading-relaxed text-muted-foreground">
                &ldquo;{decision.sourceQuote}&rdquo;
              </p>
            )}
          </Link>
        ))}
      </div>
    </div>
  )
}
