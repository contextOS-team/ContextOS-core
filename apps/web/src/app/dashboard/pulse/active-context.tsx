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

function splitBracketPrefix(title: string): { prefix: string | null; rest: string } {
  const displayTitle = title.replace(/^Context:\s*/i, '')
  const match = /^(\[[^\]]+\])+/.exec(displayTitle)
  if (!match) return { prefix: null, rest: displayTitle }
  return {
    prefix: match[0],
    rest: displayTitle.slice(match[0].length).trim(),
  }
}

function ContextRow({ item, lastVisitedAt }: { item: ContextPageRow; lastVisitedAt: Date | null }) {
  const seen = useSessionSeenItems()
  const isNew = lastVisitedAt ? new Date(item.updated_at) > lastVisitedAt : false
  const showMarker = isNew || seen.hasSeen(item.id)
  const { prefix, rest } = splitBracketPrefix(item.title)

  useEffect(() => {
    if (isNew) seen.markSeen(item.id)
  }, [item.id, isNew, seen])

  return (
    <Link
      href={`/dashboard/context/${item.id}`}
      className="relative block py-4 transition-colors hover:bg-white/[0.02]"
    >
      {showMarker && <NewItemMarker />}
      <div className="flex items-baseline gap-3">
        {item.ticket_identifier && (
          <span className="shrink-0 text-xs text-[#6e6b66]" style={{ fontFamily: 'var(--font-geist-mono)' }}>
            {item.ticket_identifier}
          </span>
        )}
        <span className="min-w-0 flex-1 truncate text-sm text-[#ece9e3]">
          {prefix && <span className="text-[#a8a59f]">{prefix} </span>}
          {rest}
        </span>
        <span className="shrink-0 text-xs text-[#6e6b66]">
          {item.sources?.length ?? 0} source{(item.sources?.length ?? 0) === 1 ? '' : 's'}
        </span>
        <span className="shrink-0 text-xs text-[#6e6b66]">
          {formatRelativeTime(item.updated_at)}
        </span>
      </div>
    </Link>
  )
}

export function ActiveContext({ items, lastVisitedAt }: ActiveContextProps) {
  const topItems = items.slice(0, 3)
  if (topItems.length === 0) return null

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="pulse-section-label">Active context</h2>
        <Link href="/dashboard/context" className="text-xs text-[#6e6b66] transition-colors hover:text-[#a8a59f]">
          view all &rarr;
        </Link>
      </div>
      <div className="divide-y divide-white/[0.04]">
        {topItems.map((item) => (
          <ContextRow key={item.id} item={item} lastVisitedAt={lastVisitedAt} />
        ))}
      </div>
    </section>
  )
}
