'use client'

import { useEffect, useState } from 'react'
import type { LensGraphResponse } from '@/components/graph/types'
import { getDashboardAttention, fetchMyWorkGraph, type AttentionItem } from '@/lib/api'
import { fetchContextPages, type ContextPageRow } from '@/lib/context-feed'
import { bucketDelta, fetchActivityDelta } from './since-last-visit/activity-delta'
import type { Delta, NeedsYouItem } from './types'

const EMPTY_DELTA: Delta = {
  decisions: { count: 0, items: [] },
  sources: { count: 0, items: [] },
  needsYou: { topUrgentItem: null, items: [] },
}

export interface DashboardData {
  decisions: LensGraphResponse | null
  contextItems: ContextPageRow[]
  needsYouItems: NeedsYouItem[]
  delta: Delta
  workspaceId: string | null
  isLoading: boolean
  error: string | null
}

export function humanizeSinceDay(date: Date, now: Date = new Date()): string {
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / 86_400_000)

  if (diffDays < 0) {
    return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(date)
  }

  if (diffDays < 7) {
    return new Intl.DateTimeFormat('en-US', { weekday: 'long' }).format(date)
  }

  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(date)
}

function estimateAttentionDate(item: AttentionItem, now: Date): Date {
  const age = item.age?.toLowerCase()
  if (!age || age === 'just now') return now

  const dayMatch = age.match(/^(\d+)\s+days?\s+ago$/)
  if (dayMatch) {
    return new Date(now.getTime() - Number(dayMatch[1]) * 86_400_000)
  }

  const hourMatch = age.match(/^(\d+)h\s+ago$/)
  if (hourMatch) {
    return new Date(now.getTime() - Number(hourMatch[1]) * 3_600_000)
  }

  return now
}

function attentionTicketId(item: AttentionItem): string {
  const maybeGitlabIid = (item as AttentionItem & { iid?: number }).iid

  if (item.ticket_identifier) return item.ticket_identifier
  if (item.repo_full_name && item.number) return `${item.repo_full_name}#${item.number}`
  if (item.project_path && maybeGitlabIid) return `${item.project_path}!${maybeGitlabIid}`
  return item.title
}

function mapAttentionItems(items: AttentionItem[], now: Date): NeedsYouItem[] {
  return items.map((item) => {
    const estimatedDate = estimateAttentionDate(item, now)
    return {
      id: item.id,
      ticketId: attentionTicketId(item),
      person: item.author ?? 'ContextOS',
      sinceDay: humanizeSinceDay(estimatedDate, now),
      assignedToCurrentUser: true,
      ageMs: Math.max(0, now.getTime() - estimatedDate.getTime()),
    }
  })
}

function firstError(results: PromiseSettledResult<unknown>[]): string | null {
  const rejected = results.find((result): result is PromiseRejectedResult => result.status === 'rejected')
  if (!rejected) return null
  return rejected.reason instanceof Error ? rejected.reason.message : 'Failed to load dashboard data'
}

export function useDashboardData(
  workspaceId: string | null,
  lastVisitedAt: Date | null
): DashboardData {
  const [data, setData] = useState<DashboardData>({
    decisions: null,
    contextItems: [],
    needsYouItems: [],
    delta: EMPTY_DELTA,
    workspaceId,
    isLoading: false,
    error: null,
  })

  useEffect(() => {
    let cancelled = false

    async function load() {
      if (!workspaceId) {
        setData({
          decisions: null,
          contextItems: [],
          needsYouItems: [],
          delta: EMPTY_DELTA,
          workspaceId: null,
          isLoading: false,
          error: null,
        })
        return
      }

      setData((current) => ({ ...current, workspaceId, isLoading: true, error: null }))

      const now = new Date()
      const results = await Promise.allSettled([
        getDashboardAttention(),
        fetchContextPages(),
        fetchMyWorkGraph(),
        fetchActivityDelta(workspaceId, lastVisitedAt),
      ])

      if (cancelled) return

      const attention = results[0].status === 'fulfilled' ? results[0].value : []
      const contextItems = results[1].status === 'fulfilled' ? results[1].value : []
      const decisions = results[2].status === 'fulfilled' ? results[2].value : null
      const activityRows = results[3].status === 'fulfilled' ? results[3].value : []
      const needsYouItems = mapAttentionItems(attention, now)

      setData({
        decisions,
        contextItems: contextItems.slice(0, 3),
        needsYouItems,
        delta: bucketDelta(activityRows, needsYouItems, ''),
        workspaceId,
        isLoading: false,
        error: firstError(results),
      })
    }

    void load()

    return () => {
      cancelled = true
    }
  }, [workspaceId, lastVisitedAt])

  return data
}
