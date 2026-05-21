'use client'

import { useEffect, useMemo } from 'react'
import Link from 'next/link'
import type { ApiNode, LensGraphResponse } from '@/components/graph/types'
import { formatRelativeTime } from '@/lib/utils'
import { useSessionSeenItems } from './since-last-visit/use-session-seen-items'
import { NewItemMarker } from './new-item-marker'

interface DecisionDisplay {
  id: string
  title: string
  participants: string[]
  sourceChannel: string | null
  authorName: string | null
  sourceQuote: string | null
  createdAt: string | null
}

interface RecentDecisionsProps {
  data: LensGraphResponse | null
  lastVisitedAt: Date | null
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim().length > 0 ? value : null
}

function parseParticipants(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
}

function parseDecisionNode(node: ApiNode): DecisionDisplay {
  const props = node.properties ?? {}
  const participants = parseParticipants(props.participants)
  return {
    id: node.id,
    title: node.name,
    participants,
    sourceChannel: asString(props.source_channel),
    authorName: asString(props.author_name) ?? participants[0] ?? null,
    sourceQuote: asString(props.source_quote),
    createdAt: asString(props.date),
  }
}

function DecisionCard({
  decision,
  lastVisitedAt,
}: {
  decision: DecisionDisplay
  lastVisitedAt: Date | null
}) {
  const seen = useSessionSeenItems()
  const isNew = decision.createdAt && lastVisitedAt
    ? new Date(decision.createdAt) > lastVisitedAt
    : false
  const showMarker = Boolean(isNew || seen.hasSeen(decision.id))

  useEffect(() => {
    if (isNew) seen.markSeen(decision.id)
  }, [decision.id, isNew, seen])

  return (
    <Link
      href={`/dashboard/decisions/${encodeURIComponent(decision.id)}`}
      className="group relative block px-5 py-4 transition-colors hover:bg-elevated/50"
    >
      {showMarker && <NewItemMarker />}
      <h3 className="text-[15px] font-medium leading-snug text-foreground group-hover:underline decoration-1 underline-offset-[0.2em]">
        {decision.title}
      </h3>

      {(decision.participants.length > 0 || decision.sourceChannel || decision.createdAt) && (
        <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
          {decision.participants.slice(0, 3).map((name) => (
            <span key={name} className="rounded-full bg-muted px-2 py-0.5 text-muted-foreground">
              {name}
            </span>
          ))}
          {decision.sourceChannel && (
            <span style={{ fontFamily: 'var(--font-geist-mono)' }}>{decision.sourceChannel}</span>
          )}
          {decision.createdAt && <span>{formatRelativeTime(decision.createdAt)}</span>}
        </div>
      )}

      {decision.sourceQuote && (
        <blockquote className="pulse-quote">
          <p className="line-clamp-2 text-sm italic leading-relaxed text-foreground">
            &ldquo;{decision.sourceQuote}&rdquo;
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            &mdash; {decision.authorName ?? 'someone'}
            {decision.sourceChannel && (
              <>
                {' '}in <span style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '0.92em' }}>{decision.sourceChannel}</span>
              </>
            )}
            {decision.createdAt && <>, {formatRelativeTime(decision.createdAt)}</>}
          </p>
        </blockquote>
      )}
    </Link>
  )
}

export function RecentDecisions({ data, lastVisitedAt }: RecentDecisionsProps) {
  const decisions = useMemo(() => {
    if (!data) return []
    return data.all_nodes
      .filter((node) => node.entity_type === 'Decision')
      .sort((a, b) => {
        const dateA = asString(a.properties?.date) ?? ''
        const dateB = asString(b.properties?.date) ?? ''
        return dateB.localeCompare(dateA)
      })
      .slice(0, 2)
      .map(parseDecisionNode)
  }, [data])

  if (decisions.length === 0) return null

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="pulse-section-label">Recent decisions</h2>
        <Link href="/dashboard/decisions" className="text-xs text-muted-foreground transition-colors hover:text-foreground">
          view all &rarr;
        </Link>
      </div>
      <div className="pulse-card divide-y divide-border/70 overflow-hidden">
        {decisions.map((decision) => (
          <DecisionCard key={decision.id} decision={decision} lastVisitedAt={lastVisitedAt} />
        ))}
      </div>
    </section>
  )
}
