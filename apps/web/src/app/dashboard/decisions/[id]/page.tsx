'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { fetchWorkspaceGraph } from '@/lib/api'
import { formatRelativeTime } from '@/lib/utils'
import { formatDecisionChannels, getDecisionPeople, toDecisionView, type DecisionNodeView } from '../decision-node'

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
      <div className="mx-auto max-w-4xl space-y-5">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-40 w-full rounded-xl" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <Link href="/dashboard/decisions" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
          Decisions
        </Link>
        <p className="text-sm text-destructive">Failed to load decision: {error}</p>
      </div>
    )
  }

  if (!decision) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <Link href="/dashboard/decisions" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
          Decisions
        </Link>
        <p className="text-sm text-muted-foreground">Decision not found.</p>
      </div>
    )
  }

  const people = getDecisionPeople(decision)
  const channels = formatDecisionChannels(decision.sourceChannel)
  const relativeTime = decision.date ? formatRelativeTime(decision.date) : null
  const confidence = decision.confidence !== null
    ? `${Math.round(decision.confidence * 100)}% confidence`
    : null

  return (
    <article className="decision-detail mx-auto max-w-5xl space-y-6 animate-fade-in-up">
      <Link href="/dashboard/decisions" className="decision-back-link">
        <ArrowLeft className="h-4 w-4" />
        Decisions
      </Link>

      <header className="space-y-4 border-b border-white/[0.06] pb-6">
        <h1 className="decision-title max-w-4xl text-2xl font-semibold leading-tight text-foreground">
          {decision.title}
        </h1>
        <div className="decision-meta">
          {decision.authorName && (
            <span className="decision-pill decision-pill--person">
              {decision.authorName}
            </span>
          )}
          {channels.map((channel) => (
            <span key={channel} className="decision-pill decision-pill--channel">
              {channel}
            </span>
          ))}
          {relativeTime && (
            <span className="decision-pill decision-pill--muted">
              {relativeTime}
            </span>
          )}
          {confidence && (
            <span className="decision-pill decision-pill--muted tabular-nums">
              {confidence}
            </span>
          )}
        </div>
      </header>

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
        <section className="space-y-4">
          {decision.sourceQuote && (
            <div className="dashboard-panel p-5">
              <p className="decision-panel-label">Source quote</p>
              <blockquote className="mt-3 border-l border-white/[0.09] pl-4 text-base leading-relaxed text-foreground">
                &ldquo;{decision.sourceQuote}&rdquo;
              </blockquote>
            </div>
          )}

          {decision.rationale && (
            <div className="dashboard-panel p-5">
              <h2 className="decision-panel-label">Rationale</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                {decision.rationale}
              </p>
            </div>
          )}
        </section>

        <aside className="space-y-3">
          {people.length > 0 && (
            <section className="dashboard-panel p-4">
              <h2 className="decision-panel-label">People</h2>
              <div className="flex flex-wrap gap-2">
                {people.map((name) => (
                  <span key={name} className="decision-pill decision-pill--person">
                    {name}
                  </span>
                ))}
              </div>
            </section>
          )}

          <section className="dashboard-panel p-4 text-sm">
            <h2 className="decision-panel-label">Source</h2>
            <dl className="mt-3 space-y-3">
              {decision.authorName && (
                <div>
                  <dt className="decision-detail-term">Author</dt>
                  <dd className="mt-1 text-foreground">{decision.authorName}</dd>
                </div>
              )}
              {channels.length > 0 && (
                <div>
                  <dt className="decision-detail-term">Channels</dt>
                  <dd className="mt-1 flex flex-wrap gap-1.5">
                    {channels.map((channel) => (
                      <span key={channel} className="decision-pill decision-pill--channel">
                        {channel}
                      </span>
                    ))}
                  </dd>
                </div>
              )}
              {relativeTime && (
                <div>
                  <dt className="decision-detail-term">Seen</dt>
                  <dd className="mt-1 text-foreground">{relativeTime}</dd>
                </div>
              )}
              {confidence && (
                <div>
                  <dt className="decision-detail-term">Confidence</dt>
                  <dd className="mt-1 tabular-nums text-foreground">{confidence}</dd>
                </div>
              )}
            </dl>
          </section>
        </aside>
      </div>
    </article>
  )
}
