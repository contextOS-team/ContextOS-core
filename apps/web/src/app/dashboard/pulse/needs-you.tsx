'use client'

import { useEffect } from 'react'
import type { NeedsYouItem } from './types'
import { useSessionSeenItems } from './since-last-visit/use-session-seen-items'
import { NewItemMarker } from './new-item-marker'

interface NeedsYouProps {
  items: NeedsYouItem[]
  lastVisitedAt: Date | null
}

function NeedsYouRow({ item, lastVisitedAt }: { item: NeedsYouItem; lastVisitedAt: Date | null }) {
  const seen = useSessionSeenItems()
  const estimatedCreatedAt = new Date(Date.now() - item.ageMs)
  const isNew = lastVisitedAt ? estimatedCreatedAt > lastVisitedAt : false
  const showMarker = isNew || seen.hasSeen(item.id)

  useEffect(() => {
    if (isNew) seen.markSeen(item.id)
  }, [item.id, isNew, seen])

  return (
    <div className="relative px-5 py-3.5">
      {showMarker && <NewItemMarker />}
      <div className="flex items-baseline gap-3">
        <span className="shrink-0 text-xs text-muted-foreground" style={{ fontFamily: 'var(--font-geist-mono)' }}>
          {item.ticketId}
        </span>
        <span className="min-w-0 flex-1 truncate text-sm text-foreground">
          {item.person} asked {item.sinceDay}
        </span>
        <span className="shrink-0 text-xs text-muted-foreground">
          {Math.max(0, Math.floor(item.ageMs / 86_400_000))}d
        </span>
      </div>
    </div>
  )
}

export function NeedsYou({ items, lastVisitedAt }: NeedsYouProps) {
  if (items.length === 0) return null

  return (
    <section className="space-y-3">
      <h2 className="pulse-section-label">Needs you</h2>
      <div className="pulse-card divide-y divide-border/70 overflow-hidden">
        {items.map((item) => (
          <NeedsYouRow key={item.id} item={item} lastVisitedAt={lastVisitedAt} />
        ))}
      </div>
    </section>
  )
}
