'use client'

import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import type { ApiNode } from '@/components/graph/types'
import {
  addMissedDecisionAsEvidence,
  deferMissedDecision,
  dismissMissedDecision,
  fetchDecisions,
  getDashboardAttention,
  getDashboardSuggestions,
  getMissedDecisionReviewSuggestions,
  ignoreMissedDecisionDuplicate,
  saveMissedDecisionAsNewDecision,
  type AttentionItem,
  type MissedDecisionReviewSuggestion,
  type SuggestionItem,
} from '@/lib/api'
import { fetchContextPages, type ContextPageRow } from '@/lib/context-feed'
import { bucketDelta, fetchActivityDelta } from './since-last-visit/activity-delta'
import type {
  Delta,
  MissedDecisionReviewActions,
  NeedsReviewSuggestionsState,
  NeedsYouItem,
} from './types'

const EMPTY_DELTA: Delta = {
  decisions: { count: 0, items: [] },
  sources: { count: 0, items: [] },
  needsYou: { topUrgentItem: null, items: [] },
}

export const DASHBOARD_REQUEST_TIMEOUT_MS = 8_000

interface DashboardDataState extends NeedsReviewSuggestionsState {
  decisions: ApiNode[] | null
  suggestions: SuggestionItem[]
  contextItems: ContextPageRow[]
  needsYouItems: NeedsYouItem[]
  delta: Delta
  workspaceId: string | null
  isLoading: boolean
  error: string | null
}

export interface DashboardData extends DashboardDataState {
  missedDecisionActions: MissedDecisionReviewActions
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

function firstError(...results: PromiseSettledResult<unknown>[]): string | null {
  const rejected = results.find((result): result is PromiseRejectedResult => result.status === 'rejected')
  if (!rejected) return null
  return rejected.reason instanceof Error ? rejected.reason.message : 'Failed to load dashboard data'
}

function settledValue<T>(result: PromiseSettledResult<T>, fallback: T): T {
  return result.status === 'fulfilled' ? result.value : fallback
}

function missedDecisionError(
  result: PromiseSettledResult<MissedDecisionReviewSuggestion[]>
): string | null {
  if (result.status === 'fulfilled') return null
  return 'Could not load missed-decision suggestions. Refresh the dashboard or open Activity to confirm the source sync completed.'
}

function withDashboardTimeout<T>(promise: Promise<T>, label: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timeoutId = setTimeout(() => {
      reject(new Error(`${label} timed out`))
    }, DASHBOARD_REQUEST_TIMEOUT_MS)

    promise.then(resolve, reject).finally(() => {
      clearTimeout(timeoutId)
    })
  })
}

export function useDashboardData(
  workspaceId: string | null,
  lastVisitedAt: Date | null
): DashboardData {
  const [data, setData] = useState<DashboardDataState>({
    decisions: null,
    suggestions: [],
    needsReviewSuggestions: [],
    needsReviewError: null,
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
          suggestions: [],
          needsReviewSuggestions: [],
          needsReviewError: null,
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
      const [
        attentionResult,
        suggestionsResult,
        contextItemsResult,
        decisionsResult,
        activityRowsResult,
        missedDecisionsResult,
      ] = await Promise.allSettled([
        withDashboardTimeout(getDashboardAttention(), 'Dashboard attention'),
        withDashboardTimeout(getDashboardSuggestions(3), 'Dashboard suggestions'),
        withDashboardTimeout(fetchContextPages(), 'Dashboard context'),
        withDashboardTimeout(fetchDecisions(20), 'Dashboard decisions'),
        withDashboardTimeout(
          fetchActivityDelta(workspaceId, lastVisitedAt),
          'Dashboard activity'
        ),
        withDashboardTimeout(
          getMissedDecisionReviewSuggestions(5),
          'Missed-decision suggestions'
        ),
      ])

      if (cancelled) return

      const attention = settledValue(attentionResult, [])
      const suggestions = settledValue(suggestionsResult, [])
      const contextItems = settledValue(contextItemsResult, [])
      const decisions = settledValue(decisionsResult, null)
      const activityRows = settledValue(activityRowsResult, [])
      const needsReviewSuggestions = settledValue(missedDecisionsResult, [])
      const needsYouItems = mapAttentionItems(attention, now)

      setData({
        decisions,
        suggestions,
        needsReviewSuggestions,
        needsReviewError: missedDecisionError(missedDecisionsResult),
        contextItems: contextItems.slice(0, 3),
        needsYouItems,
        delta: bucketDelta(activityRows, needsYouItems, ''),
        workspaceId,
        isLoading: false,
        error: firstError(
          attentionResult,
          contextItemsResult,
          decisionsResult,
          activityRowsResult,
        ),
      })
    }

    void load()

    return () => {
      cancelled = true
    }
  }, [workspaceId, lastVisitedAt])

  const removeMissedDecision = useCallback((candidateId: string) => {
    setData((current) => ({
      ...current,
      needsReviewSuggestions: current.needsReviewSuggestions.filter(
        (item) => item.id !== candidateId
      ),
    }))
  }, [])

  const saveAsNewDecision = useCallback(async (candidateId: string) => {
    await saveMissedDecisionAsNewDecision(candidateId)
    removeMissedDecision(candidateId)
    toast.success('Saved as decision receipt.')
  }, [removeMissedDecision])

  const addAsEvidence = useCallback(async (candidateId: string) => {
    await addMissedDecisionAsEvidence(candidateId)
    removeMissedDecision(candidateId)
    toast.success('Added evidence to the existing decision.')
  }, [removeMissedDecision])

  const deferCandidate = useCallback(async (candidateId: string) => {
    await deferMissedDecision(candidateId)
    removeMissedDecision(candidateId)
    toast.success('Deferred from review.')
  }, [removeMissedDecision])

  const dismissCandidate = useCallback(async (candidateId: string) => {
    await dismissMissedDecision(candidateId)
    removeMissedDecision(candidateId)
  }, [removeMissedDecision])

  const ignoreDuplicate = useCallback(async (candidateId: string) => {
    await ignoreMissedDecisionDuplicate(candidateId)
    removeMissedDecision(candidateId)
  }, [removeMissedDecision])

  return {
    ...data,
    missedDecisionActions: {
      saveAsNewDecision,
      addAsEvidence,
      defer: deferCandidate,
      dismiss: dismissCandidate,
      ignoreDuplicate,
    },
  }
}
