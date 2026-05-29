'use client'

import { useEffect, useMemo } from 'react'
import Link from 'next/link'
import type { ApiNode } from '@/components/graph/types'
import { formatRelativeTime } from '@/lib/utils'
import {
  formatDecisionChannels,
  getDecisionPeople,
  getDecisionRecencyDate,
  sortDecisions,
  toDecisionView,
  type DecisionNodeView,
} from '../decisions/decision-node'
import { useSessionSeenItems } from './since-last-visit/use-session-seen-items'
import { NewItemMarker } from './new-item-marker'

interface RecentDecisionsProps {
  data: ApiNode[] | null
  lastVisitedAt: Date | null
}

function decisionNodesFromData(data: unknown): ApiNode[] {
  if (!data) return []
  if (Array.isArray(data)) return data as ApiNode[]

  const legacyNodes = (data as { all_nodes?: unknown }).all_nodes
  return Array.isArray(legacyNodes) ? (legacyNodes as ApiNode[]) : []
}

export function getRecentDecisionItems(data: ApiNode[] | null): DecisionNodeView[] {
  return decisionNodesFromData(data)
    .filter((node) => {
      if (node.entity_type !== 'Decision') return false
      const status = node.properties?.status
      return (
        status === undefined
        || status === null
        || status === 'active'
        || status === 'confirmed'
      )
    })
    .map(toDecisionView)
    .sort(sortDecisions)
    .slice(0, 2)
}

function DecisionCard({
  decision,
  lastVisitedAt,
}: {
  decision: DecisionNodeView
  lastVisitedAt: Date | null
}) {
  const seen = useSessionSeenItems()
  const recencyDate = getDecisionRecencyDate(decision)
  const isNew = recencyDate && lastVisitedAt
    ? new Date(recencyDate) > lastVisitedAt
    : false
  const showMarker = Boolean(isNew || seen.hasSeen(decision.id))

  useEffect(() => {
    if (isNew) seen.markSeen(decision.id)
  }, [decision.id, isNew, seen])

  const people = getDecisionPeople(decision).slice(0, 2)
  const channels = formatDecisionChannels(decision.sourceChannel)
  const visibleChannels = channels.slice(0, 2)
  const hiddenChannelCount = Math.max(0, channels.length - visibleChannels.length)
  const relativeTime = recencyDate ? formatRelativeTime(recencyDate) : null
  const sourceRelativeTime = decision.date ? formatRelativeTime(decision.date) : null

  return (
    <Link
      href={`/dashboard/decisions/${encodeURIComponent(decision.id)}`}
      className="pulse-card pulse-row group relative block px-6 py-5 transition-colors"
    >
      {showMarker && <NewItemMarker />}
      <h3 className="pulse-title text-[16px] font-medium leading-snug text-[var(--pulse-foreground)]">
        {decision.title}
      </h3>

      {(people.length > 0 || visibleChannels.length > 0 || relativeTime) && (
        <div className="pulse-provenance mt-3">
          {people.length > 0 && (
            <span className="pulse-people">{people.join(', ')}</span>
          )}
          {visibleChannels.map((channel) => (
            <span key={channel} className="pulse-channel">
              {channel}
            </span>
          ))}
          {hiddenChannelCount > 0 && (
            <span className="pulse-channel pulse-channel--more">
              +{hiddenChannelCount}
            </span>
          )}
          {relativeTime && <span className="pulse-time">{relativeTime}</span>}
        </div>
      )}

      {decision.sourceQuote && (
        <blockquote className="pulse-quote">
          <p className="line-clamp-2 text-sm italic leading-relaxed text-[var(--pulse-foreground)]">
            &ldquo;{decision.sourceQuote}&rdquo;
          </p>
          <p className="mt-2 text-xs text-[var(--pulse-muted)]">
            &mdash; {decision.authorName ?? 'someone'}
            {channels.length > 0 && (
              <>
                {' '}in <span className="pulse-mono">{channels.join(', ')}</span>
              </>
            )}
            {sourceRelativeTime && <>, {sourceRelativeTime}</>}
          </p>
        </blockquote>
      )}
    </Link>
  )
}

export function RecentDecisions({ data, lastVisitedAt }: RecentDecisionsProps) {
  const decisions = useMemo(() => getRecentDecisionItems(data), [data])

  if (decisions.length === 0) return null

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="pulse-section-label">Recent decisions</h2>
        <Link href="/dashboard/decisions" className="pulse-section-link">
          View all
        </Link>
      </div>
      <div className="space-y-2.5">
        {decisions.map((decision) => (
          <DecisionCard key={decision.id} decision={decision} lastVisitedAt={lastVisitedAt} />
        ))}
      </div>
    </section>
  )
}
