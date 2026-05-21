'use client'

import { useEffect } from 'react'
import Link from 'next/link'
import type { ContextPageRow } from '@/lib/context-feed'
import { formatRelativeTime } from '@/lib/utils'
import { useSessionSeenItems } from './since-last-visit/use-session-seen-items'
import { NewItemMarker } from './new-item-marker'

interface ActiveContextProps {
  items: ContextPageRow[]
  lastVisitedAt: Date | null
}

const CONTEXT_ACTIVE_WINDOW_MS = 14 * 86_400_000

function splitBracketPrefix(title: string): { prefix: string | null; rest: string } {
  const displayTitle = title.replace(/^Context:\s*/i, '')
  const match = /^(\[[^\]]+\])+/.exec(displayTitle)
  if (!match) return { prefix: null, rest: displayTitle }
  return {
    prefix: match[0],
    rest: displayTitle.slice(match[0].length).trim(),
  }
}

function parseBracketTags(prefix: string | null): string[] {
  if (!prefix) return []
  return Array.from(prefix.matchAll(/\[([^\]]+)\]/g), (match) => match[1])
}

function isContextDormant(item: ContextPageRow, now = new Date()): boolean {
  const updatedAtMs = new Date(item.updated_at).getTime()
  return Number.isFinite(updatedAtMs)
    && now.getTime() - updatedAtMs > CONTEXT_ACTIVE_WINDOW_MS
}

function ContextRow({
  item,
  lastVisitedAt,
  isDormant,
}: {
  item: ContextPageRow
  lastVisitedAt: Date | null
  isDormant: boolean
}) {
  const seen = useSessionSeenItems()
  const isNew = lastVisitedAt ? new Date(item.updated_at) > lastVisitedAt : false
  const showMarker = isNew || seen.hasSeen(item.id)
  const { prefix, rest } = splitBracketPrefix(item.title)
  const tags = parseBracketTags(prefix)
  const sourceCount = item.sources?.length ?? 0

  useEffect(() => {
    if (isNew) seen.markSeen(item.id)
  }, [item.id, isNew, seen])

  return (
    <Link
      href={`/dashboard/context/${item.id}`}
      className={`pulse-card pulse-row pulse-context-card relative block px-6 py-5 transition-colors ${isDormant ? 'pulse-row--dormant' : ''}`}
    >
      {showMarker && <NewItemMarker />}
      <div className="pulse-context-topline">
        {item.ticket_identifier && (
          <span className="pulse-ticket">
            {item.ticket_identifier}
          </span>
        )}
        <span className="pulse-context-time">
          {formatRelativeTime(item.updated_at)}
        </span>
      </div>
      <p className="pulse-title mt-2 truncate text-[16px] font-medium leading-snug text-[var(--pulse-foreground)]">
        {rest}
      </p>
      <div className="pulse-context-evidence mt-3">
        {tags.map((tag) => (
          <span key={tag} className="pulse-tag">{tag}</span>
        ))}
        <span className="pulse-source-count">
          {sourceCount} source{sourceCount === 1 ? '' : 's'}
        </span>
        {isDormant && <span className="pulse-dormant-badge">dormant</span>}
      </div>
    </Link>
  )
}

export function ActiveContext({ items, lastVisitedAt }: ActiveContextProps) {
  const topItems = items.slice(0, 3)
  if (topItems.length === 0) return null
  const now = new Date()
  const rows = topItems.map((item) => ({
    item,
    isDormant: isContextDormant(item, now),
  }))
  const activeRows = rows.filter((row) => !row.isDormant)
  const dormantRows = rows.filter((row) => row.isDormant)
  const visibleRows = activeRows.length > 0 ? activeRows : dormantRows
  const hiddenDormantCount = activeRows.length > 0 ? dormantRows.length : 0

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="pulse-section-label">
          {activeRows.length > 0 ? 'Active context' : 'Context to revisit'}
        </h2>
        <Link href="/dashboard/context" className="pulse-section-link">
          View all
        </Link>
      </div>
      <div className="space-y-2.5">
        {visibleRows.map(({ item, isDormant }) => (
          <ContextRow
            key={item.id}
            item={item}
            lastVisitedAt={lastVisitedAt}
            isDormant={isDormant}
          />
        ))}
        {hiddenDormantCount > 0 && (
          <Link href="/dashboard/context" className="pulse-context-hidden-link">
            {hiddenDormantCount} older context {hiddenDormantCount === 1 ? 'item' : 'items'} hidden
          </Link>
        )}
      </div>
    </section>
  )
}
