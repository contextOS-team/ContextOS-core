'use client'

import { useEffect, useState } from 'react'
import { Skeleton } from '@/components/ui/skeleton'
import { createClient } from '@/lib/supabase/client'
import { ActiveContext } from './pulse/active-context'
import { DecisionScanProgress } from './pulse/decision-scan-progress'
import { Headline } from './pulse/headline'
import { NeedsYou } from './pulse/needs-you'
import { NeedsReview } from './pulse/needs-review'
import { NeedsReviewSuggestions } from './pulse/needs-review-suggestions'
import { RecentDecisions } from './pulse/recent-decisions'
import { SourceUpdates } from './pulse/source-updates'
import { useLastVisitedAt } from './pulse/since-last-visit/use-last-visited-at'
import { SeenItemsProvider } from './pulse/since-last-visit/use-session-seen-items'
import { useDashboardData } from './pulse/use-dashboard-data'
import { WorkspaceSnapshot } from './pulse/workspace-snapshot'

export default function DashboardPage() {
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const [isWorkspaceLoading, setIsWorkspaceLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function loadWorkspace() {
      const supabase = createClient()
      const {
        data: { user },
      } = await supabase.auth.getUser()

      if (!user) {
        if (!cancelled) setIsWorkspaceLoading(false)
        return
      }

      const { data } = await supabase
        .from('workspace_members')
        .select('workspace_id')
        .eq('user_id', user.id)
        .single()

      if (!cancelled) {
        setWorkspaceId(data?.workspace_id ?? null)
        setIsWorkspaceLoading(false)
      }
    }

    void loadWorkspace()

    return () => {
      cancelled = true
    }
  }, [])

  const lastVisitedAt = useLastVisitedAt(workspaceId)

  return (
    <SeenItemsProvider>
      <div className="pulse-surface space-y-8">
        <DashboardSections
          workspaceId={workspaceId}
          lastVisitedAt={lastVisitedAt}
          isWorkspaceLoading={isWorkspaceLoading}
        />
      </div>
    </SeenItemsProvider>
  )
}

function DashboardSections({
  workspaceId,
  lastVisitedAt,
  isWorkspaceLoading,
}: {
  workspaceId: string | null
  lastVisitedAt: Date | null
  isWorkspaceLoading: boolean
}) {
  const {
    decisions,
    suggestions,
    needsReviewSuggestions,
    needsReviewError,
    missedDecisionScans,
    missedDecisionActions,
    contextItems,
    needsYouItems,
    workspaceSnapshot,
    delta,
    isLoading,
    error,
  } = useDashboardData(workspaceId, lastVisitedAt)

  if (isWorkspaceLoading || isLoading) {
    return (
      <>
        <div>
          <Skeleton className="h-12 w-full max-w-xl" />
          <Skeleton className="mt-6 h-4 w-64" />
        </div>
        <section className="space-y-5">
          <Skeleton className="h-4 w-36" />
          <div className="space-y-4">
            <Skeleton className="h-36 w-full rounded-xl" />
            <Skeleton className="h-36 w-full rounded-xl" />
          </div>
        </section>
      </>
    )
  }

  if (error) {
    return (
      <p className="text-sm text-destructive">
        Failed to load dashboard: {error}
      </p>
    )
  }

  const hasRightRailContent = Boolean(
    missedDecisionScans.length
    || needsReviewSuggestions.length
    || needsReviewError
    || suggestions.length
    || contextItems.length
    || needsYouItems.length
  )
  const primaryColumn = (
    <div className="space-y-6">
      <RecentDecisions data={decisions} lastVisitedAt={lastVisitedAt} />
      <SourceUpdates items={delta.sources.items} />
      <WorkspaceSnapshot items={workspaceSnapshot} />
    </div>
  )

  const rightRail = (
    <div className="space-y-6">
      <DecisionScanProgress scans={missedDecisionScans} />
      {needsReviewSuggestions.length > 0 || needsReviewError ? (
        <NeedsReviewSuggestions
          suggestions={needsReviewSuggestions}
          error={needsReviewError}
          workspaceId={workspaceId}
          onSaveAsNewDecision={missedDecisionActions.saveAsNewDecision}
          onAddAsEvidence={missedDecisionActions.addAsEvidence}
          onDefer={missedDecisionActions.defer}
          onDismiss={missedDecisionActions.dismiss}
          onIgnoreDuplicate={missedDecisionActions.ignoreDuplicate}
        />
      ) : (
        <NeedsReview items={suggestions} />
      )}
      <ActiveContext items={contextItems} lastVisitedAt={lastVisitedAt} />
      <NeedsYou items={needsYouItems} lastVisitedAt={lastVisitedAt} />
    </div>
  )

  return (
    <>
      <Headline
        delta={delta}
        lastVisitedAt={lastVisitedAt}
      />
      {hasRightRailContent ? (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(340px,420px)]">
          {primaryColumn}
          {rightRail}
        </div>
      ) : (
        primaryColumn
      )}
    </>
  )
}
