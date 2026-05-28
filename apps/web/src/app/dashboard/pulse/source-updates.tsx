'use client'

import Link from 'next/link'
import {
  CheckCircle2,
  FilePlus,
  GitMerge,
  Mic,
  Plug,
  RefreshCw,
  TicketPlus,
  type LucideIcon,
} from 'lucide-react'
import { formatRelativeTime } from '@/lib/utils'
import type { SourceUpdateItem } from './types'

interface SourceUpdatesProps {
  items: ReadonlyArray<SourceUpdateItem>
  limit?: number
}

const PROVIDER_LABELS: Record<string, string> = {
  fathom: 'Fathom',
  github: 'GitHub',
  gitlab: 'GitLab',
  jira: 'Jira',
  linear: 'Linear',
  notion: 'Notion',
  slack: 'Slack',
  telegram: 'Telegram',
}

const EVENT_ICONS: Record<string, LucideIcon> = {
  integration_connected: Plug,
  meeting_recorded: Mic,
  page_created: FilePlus,
  pr_merged: GitMerge,
  sync_completed: CheckCircle2,
  ticket_created: TicketPlus,
}

function textValue(value: unknown): string | null {
  return typeof value === 'string' && value.trim().length > 0 ? value.trim() : null
}

function numberValue(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function providerLabel(metadata: Record<string, unknown>): string {
  const raw = textValue(metadata.integration)
  if (!raw) return 'Source'
  return PROVIDER_LABELS[raw.toLowerCase()] ?? raw
}

function sourceNoun(provider: string, count: number): string {
  const singular = (() => {
    switch (provider.toLowerCase()) {
      case 'github':
      case 'gitlab':
        return 'pull request'
      case 'jira':
      case 'linear':
        return 'ticket'
      case 'notion':
        return 'page'
      case 'telegram':
      case 'slack':
        return 'message'
      case 'fathom':
        return 'transcript'
      default:
        return 'record'
    }
  })()

  return `${singular}${count === 1 ? '' : 's'}`
}

function updateTitle(item: SourceUpdateItem): string {
  const provider = providerLabel(item.metadata)
  const isError = item.metadata.error === true

  switch (item.eventType) {
    case 'integration_connected':
      return `${provider} connected`
    case 'sync_completed':
      return isError ? `${provider} sync failed` : `${provider} sync completed`
    case 'ticket_created':
      return `New ${provider} ticket`
    case 'pr_merged':
      return 'Pull request merged'
    case 'meeting_recorded':
      return 'Meeting recorded'
    case 'page_created':
      return 'Page added'
    default:
      return `${provider} updated`
  }
}

function updateDetail(item: SourceUpdateItem): string {
  const { metadata } = item
  const provider = providerLabel(metadata)
  const itemCount = numberValue(metadata.items_count)

  switch (item.eventType) {
    case 'integration_connected': {
      const chatTitle = textValue(metadata.chat_title)
      return chatTitle ? `${chatTitle} is now available as a source.` : 'The source is connected and ready.'
    }
    case 'sync_completed':
      if (metadata.error === true) {
        return textValue(metadata.error_message) ?? 'The sync paused before completing.'
      }
      if (itemCount !== null) {
        return itemCount === 0
          ? 'No new records imported.'
          : `${itemCount.toLocaleString('en-US')} ${sourceNoun(provider, itemCount)} imported.`
      }
      return 'Source data finished syncing.'
    case 'ticket_created': {
      const ticketId = textValue(metadata.ticket_id)
      const title = textValue(metadata.title)
      return [ticketId, title].filter(Boolean).join(' - ') || 'A new ticket was imported.'
    }
    case 'pr_merged': {
      const repo = textValue(metadata.repo)
      const prNumber = metadata.pr_number ? `#${metadata.pr_number}` : null
      const title = textValue(metadata.title)
      return [repo, prNumber, title].filter(Boolean).join(' ') || 'A pull request was imported.'
    }
    case 'meeting_recorded':
      return textValue(metadata.title) ?? 'A meeting transcript was imported.'
    case 'page_created':
      return textValue(metadata.page_title) ?? 'A page was imported.'
    default:
      return 'New source activity was imported.'
  }
}

function SourceUpdateRow({ item }: { item: SourceUpdateItem }) {
  const Icon = EVENT_ICONS[item.eventType] ?? RefreshCw
  const relativeTime = formatRelativeTime(item.createdAt)

  return (
    <Link
      href="/dashboard/activity"
      className="pulse-row flex items-start gap-3 px-4 py-3.5 transition-colors"
    >
      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/[0.045] text-[var(--pulse-muted)]">
        <Icon className="size-4" aria-hidden="true" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="pulse-title text-sm font-medium leading-5 text-[var(--pulse-foreground)]">
            {updateTitle(item)}
          </span>
          <span className="pulse-time text-xs">{relativeTime}</span>
        </span>
        <span className="mt-1 block line-clamp-2 text-sm leading-5 text-[var(--pulse-muted)]">
          {updateDetail(item)}
        </span>
      </span>
    </Link>
  )
}

export function SourceUpdates({ items, limit = 4 }: SourceUpdatesProps) {
  if (items.length === 0) return null

  const visible = items.slice(0, Math.max(0, limit))
  const hiddenCount = Math.max(0, items.length - visible.length)

  return (
    <section className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <h2 className="pulse-section-label">Source updates</h2>
          <p className="text-sm leading-6 text-[var(--pulse-muted)]">
            Latest imported activity since your last visit.
          </p>
        </div>
        <Link href="/dashboard/activity" className="pulse-section-link -mt-2">
          View activity
        </Link>
      </div>
      <div className="pulse-list-panel">
        {visible.map((item) => (
          <SourceUpdateRow key={item.id} item={item} />
        ))}
        {hiddenCount > 0 && (
          <Link href="/dashboard/activity" className="pulse-list-footer">
            View {hiddenCount} more source {hiddenCount === 1 ? 'update' : 'updates'}
          </Link>
        )}
      </div>
    </section>
  )
}
