'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
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
  getMissedDecisionScanStatus,
  getMissedDecisionReviewSuggestions,
  ignoreMissedDecisionDuplicate,
  saveMissedDecisionAsNewDecision,
  type AttentionItem,
  type GithubIndexStatus,
  type GithubSyncStatus,
  type IntegrationStatusResponse,
  type LinearSyncStatus,
  type MissedDecisionActionResponse,
  type MissedDecisionReviewSuggestion,
  type MissedDecisionScanStatus,
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
const GENERIC_REVIEW_SUGGESTION_LIMIT = 3

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

function genericReviewSuggestions(suggestions: SuggestionItem[]): SuggestionItem[] {
  return suggestions
    .filter((suggestion) => suggestion.type !== 'missed_decision')
    .slice(0, GENERIC_REVIEW_SUGGESTION_LIMIT)
}

function missedDecisionError(
  result: PromiseSettledResult<MissedDecisionReviewSuggestion[]>
): string | null {
  if (result.status === 'fulfilled') return null
  return 'Could not load missed-decision suggestions. Refresh the dashboard or open Activity to confirm the source sync completed.'
}

function hasActiveScan(scans: MissedDecisionScanStatus[]): boolean {
  return scans.some((scan) => scan.status === 'queued' || scan.status === 'running')
}

function activeCandidateSignature(scans: MissedDecisionScanStatus[]): string {
  return scans
    .filter((scan) => (
      (scan.status === 'queued' || scan.status === 'running')
      && scan.review_candidates > 0
    ))
    .map((scan) => `${scan.id}:${scan.review_candidates}`)
    .join('|')
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

function missedDecisionActionToDecisionNode(
  result: MissedDecisionActionResponse
): ApiNode | null {
  if (!result.decision_node_id) return null

  return {
    id: result.decision_node_id,
    entity_type: 'Decision',
    name: result.inferred_decision,
    depth: 0,
    created_at: new Date().toISOString(),
    properties: {
      description: result.inferred_decision,
      rationale: result.inferred_rationale,
      source_quote: result.source_quote,
      source_link: result.source_link,
      confidence: result.confidence,
      author_name: result.author_name,
      participants: result.people,
      source_channel: result.source_channel,
      source_context: result.source_context,
      affected_systems: result.affected_systems,
      candidate_id: result.id,
      status: 'confirmed',
      model: 'missed_decision:v1',
    },
  }
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
  const refreshedCompletedScanIds = useRef<Set<string>>(new Set())
  const refreshedCandidateProgressSignature = useRef('')
  const [data, setData] = useState<DashboardDataState>({
    decisions: null,
    suggestions: [],
    needsReviewSuggestions: [],
    needsReviewError: null,
    missedDecisionScans: [],
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
          missedDecisionScans: [],
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
        missedDecisionScansResult,
        integrationStatusResult,
        linearStatusResult,
        githubStatusResult,
        githubIndexStatusResult,
      ] = await Promise.allSettled([
        withDashboardTimeout(getDashboardAttention(), 'Dashboard attention'),
        withDashboardTimeout(
          getDashboardSuggestions(GENERIC_REVIEW_SUGGESTION_LIMIT, {
            excludeTypes: ['missed_decision'],
          }),
          'Dashboard suggestions'
        ),
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
        withDashboardTimeout(
          getMissedDecisionScanStatus(),
          'Missed-decision scan status'
        ),
        withDashboardTimeout(getIntegrationStatus(), 'Integration status'),
        withDashboardTimeout(getLinearSyncStatus(), 'Linear sync status'),
        withDashboardTimeout(getGithubSyncStatus(), 'GitHub sync status'),
        withDashboardTimeout(getGithubIndexStatus(), 'GitHub index status'),
      ])

      if (cancelled) return

      const attention = settledValue(attentionResult, [])
      const suggestions = genericReviewSuggestions(settledValue(suggestionsResult, []))
      const contextItems = settledValue(contextItemsResult, [])
      const decisions = settledValue(decisionsResult, null)
      const activityRows = settledValue(activityRowsResult, [])
      const needsReviewSuggestions = settledValue(missedDecisionsResult, [])
      const missedDecisionScans = settledValue(missedDecisionScansResult, [])
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
        missedDecisionScans,
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

  useEffect(() => {
    refreshedCompletedScanIds.current.clear()
    refreshedCandidateProgressSignature.current = ''
  }, [workspaceId])

  useEffect(() => {
    if (!workspaceId || !hasActiveScan(data.missedDecisionScans)) return
    let cancelled = false

    async function pollScans() {
      let scans: MissedDecisionScanStatus[]
      try {
        scans = await getMissedDecisionScanStatus()
      } catch {
        return
      }

      if (cancelled) return

      const newlyCompleted = scans.filter(
        (scan) => scan.status === 'succeeded'
          && !refreshedCompletedScanIds.current.has(scan.id)
      )
      const candidateSignature = activeCandidateSignature(scans)
      const hasNewCandidateProgress = Boolean(
        candidateSignature
        && candidateSignature !== refreshedCandidateProgressSignature.current
      )
      if (newlyCompleted.length === 0 && !hasNewCandidateProgress) {
        setData((current) => ({
          ...current,
          missedDecisionScans: scans,
        }))
        return
      }

      try {
        const suggestions = await getMissedDecisionReviewSuggestions(5)
        if (cancelled) return
        for (const scan of newlyCompleted) {
          refreshedCompletedScanIds.current.add(scan.id)
        }
        if (candidateSignature) {
          refreshedCandidateProgressSignature.current = candidateSignature
        }
        setData((current) => ({
          ...current,
          missedDecisionScans: scans,
          needsReviewSuggestions: suggestions,
          needsReviewError: null,
        }))
      } catch {
        if (cancelled) return
        setData((current) => ({
          ...current,
          missedDecisionScans: scans,
          needsReviewError: 'Could not load missed-decision suggestions. Refresh the dashboard or open Activity to confirm the source sync completed.',
        }))
      }
    }

    const intervalId = window.setInterval(() => {
      void pollScans()
    }, 5_000)

    return () => {
      cancelled = true
      window.clearInterval(intervalId)
    }
  }, [workspaceId, data.missedDecisionScans])

  const removeMissedDecision = useCallback((candidateId: string) => {
    setData((current) => ({
      ...current,
      needsReviewSuggestions: current.needsReviewSuggestions.filter(
        (item) => item.id !== candidateId
      ),
    }))
  }, [])

  const saveAsNewDecision = useCallback(async (candidateId: string) => {
    const result = await saveMissedDecisionAsNewDecision(candidateId)
    removeMissedDecision(candidateId)
    const optimisticDecision = missedDecisionActionToDecisionNode(result)
    if (optimisticDecision) {
      setData((current) => ({
        ...current,
        decisions: [
          optimisticDecision,
          ...(current.decisions ?? []).filter((node) => node.id !== optimisticDecision.id),
        ].slice(0, 20),
      }))
    }
    try {
      const decisions = await fetchDecisions(20)
      setData((current) => ({ ...current, decisions }))
    } catch {
      // The action succeeded; keep the optimistic decision visible if refresh fails.
    }
    toast.success('Saved as decision receipt.')
  }, [removeMissedDecision])

  const addAsEvidence = useCallback(async (
    candidateId: string,
    targetDecisionId?: string | null
  ) => {
    await addMissedDecisionAsEvidence(candidateId, targetDecisionId)
    removeMissedDecision(candidateId)
    toast.success('Added evidence to the existing decision.')
  }, [removeMissedDecision])

  const deferCandidate = useCallback(async (candidateId: string) => {
    await deferMissedDecision(candidateId)
    removeMissedDecision(candidateId)
    toast.success('Deferred from review.')
  }, [removeMissedDecision])

  const dismissCandidate = useCallback(async (
    candidateId: string,
    reason?: string | null
  ) => {
    await dismissMissedDecision(candidateId, reason)
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
