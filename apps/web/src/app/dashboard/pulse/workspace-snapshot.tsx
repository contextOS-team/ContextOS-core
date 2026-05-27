'use client'

import Link from 'next/link'
import type { WorkspaceSnapshotItem } from './types'

interface WorkspaceSnapshotProps {
  items: WorkspaceSnapshotItem[]
}

function SnapshotMetric({ item }: { item: WorkspaceSnapshotItem }) {
  const content = (
    <>
      <span className="pulse-section-label">{item.label}</span>
      <span className="mt-4 block text-2xl font-semibold leading-none text-[var(--pulse-foreground)]">
        {item.value}
      </span>
      <span className="mt-2 block text-sm leading-5 text-[var(--pulse-muted)]">
        {item.detail}
      </span>
    </>
  )

  if (!item.href) {
    return (
      <div className="pulse-card px-5 py-4">
        {content}
      </div>
    )
  }

  return (
    <Link
      href={item.href}
      className="pulse-card pulse-row block px-5 py-4 transition-colors"
    >
      {content}
    </Link>
  )
}

export function WorkspaceSnapshot({ items }: WorkspaceSnapshotProps) {
  if (items.length === 0) return null

  return (
    <section className="space-y-3">
      <h2 className="pulse-section-label">Workspace snapshot</h2>
      <div className="grid gap-2.5 sm:grid-cols-3">
        {items.map((item) => (
          <SnapshotMetric key={item.id} item={item} />
        ))}
      </div>
    </section>
  )
}
