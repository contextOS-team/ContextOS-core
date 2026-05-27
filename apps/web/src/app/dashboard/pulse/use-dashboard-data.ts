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
  getGithubIndexStatus,
  getGithubSyncStatus,
  getIntegrationStatus,
  getLinearSyncStatus,
  getMissedDecisionReviewSuggestions,
  ignoreMissedDecisionDuplicate,
  saveMissedDecisionAsNewDecision,
  type AttentionItem,
  type GithubIndexStatus,
  type GithubSyncStatus,
  type IntegrationStatusResponse,
  type LinearSyncStatus,
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
  WorkspaceSnapshotItem,
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
  workspaceSnapshot: WorkspaceSnapshotItem[]
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

function formatCount(value: number): string {
  return new Intl.NumberFormat('en-US').format(value)
}

function pluralDetail(count: number, singular: string): string {
  return `${singular}${count === 1 ? '' : 's'}`
}

function syncedRepoCount(github: GithubSyncStatus | null): number {
  if (!github) return 0
  return Object.values(github.repo_sync_status)
    .filter((row) => row.status.toLowerCase() === 'synced')
    .length
}

export function buildWorkspaceSnapshot({
  integrations,
  linear,
  github,
  githubIndex,
}: {
  integrations: IntegrationStatusResponse | null
  linear: LinearSyncStatus | null
  github: GithubSyncStatus | null
  githubIndex: GithubIndexStatus | null
}): WorkspaceSnapshotItem[] {
  const items: WorkspaceSnapshotItem[] = []

  if (integrations?.linear.status === 'connected' && linear?.tickets_synced) {
    items.push({
      id: 'linear',
      label: 'Linear',
      value: formatCount(linear.tickets_synced),
      detail: `${pluralDetail(linear.tickets_synced, 'ticket')} imported`,
      href: '/dashboard/context',
    })
  }

  const indexedChunks = (githubIndex?.repos ?? [])
    .reduce((sum, repo) => sum + Math.max(0, repo.chunks), 0)
  if (integrations?.github.status === 'connected' && indexedChunks > 0) {
    items.push({
      id: 'github-code',
      label: 'GitHub',
      value: formatCount(indexedChunks),
      detail: 'code chunks indexed',
      href: '/dashboard/graph',
    })
  }

  const reposSynced = syncedRepoCount(github)
  if (
    integrations?.github.status === 'connected'
    && reposSynced > 0
    && indexedChunks === 0
  ) {
    items.push({
      id: 'github-repos',
      label: 'GitHub',
      value: formatCount(reposSynced),
      detail: `${pluralDetail(reposSynced, 'repo')} synced`,
      href: '/dashboard/settings?tab=integrations',
    })
  }

  if (integrations?.telegram.status === 'connected') {
    items.push({
      id: 'telegram',
      label: 'Telegram',
      value: '1',
      detail: 'chat connected',
      href: '/dashboard/activity',
    })
  }

  return items.slice(0, 3)
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
    workspaceSnapshot: [],
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
          workspaceSnapshot: [],
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
        integrationStatusResult,
        linearStatusResult,
        githubStatusResult,
        githubIndexStatusResult,
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
        withDashboardTimeout(getIntegrationStatus(), 'Integration status'),
        withDashboardTimeout(getLinearSyncStatus(), 'Linear sync status'),
        withDashboardTimeout(getGithubSyncStatus(), 'GitHub sync status'),
        withDashboardTimeout(getGithubIndexStatus(), 'GitHub index status'),
      ])

      if (cancelled) return

      const attention = settledValue(attentionResult, [])
      const suggestions = settledValue(suggestionsResult, [])
      const contextItems = settledValue(contextItemsResult, [])
      const decisions = settledValue(decisionsResult, null)
      const activityRows = settledValue(activityRowsResult, [])
      const needsReviewSuggestions = settledValue(missedDecisionsResult, [])
      const integrations = settledValue(integrationStatusResult, null)
      const linear = settledValue(linearStatusResult, null)
      const github = settledValue(githubStatusResult, null)
      const githubIndex = settledValue(githubIndexStatusResult, null)
      const needsYouItems = mapAttentionItems(attention, now)

      setData({
        decisions,
        suggestions,
        needsReviewSuggestions,
        needsReviewError: missedDecisionError(missedDecisionsResult),
        contextItems: contextItems.slice(0, 3),
        needsYouItems,
        workspaceSnapshot: buildWorkspaceSnapshot({
          integrations,
          linear,
          github,
          githubIndex,
        }),
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
