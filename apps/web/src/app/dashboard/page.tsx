'use client'

import { useEffect, useState } from 'react'
import { Skeleton } from '@/components/ui/skeleton'
import { createClient } from '@/lib/supabase/client'
import { ActiveContext } from './pulse/active-context'
import { Headline } from './pulse/headline'
import { NeedsYou } from './pulse/needs-you'
import { RecentDecisions } from './pulse/recent-decisions'
import { useLastVisitedAt } from './pulse/since-last-visit/use-last-visited-at'
import { SeenItemsProvider } from './pulse/since-last-visit/use-session-seen-items'
import { useDashboardData } from './pulse/use-dashboard-data'

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
      <main className="pulse-surface relative left-1/2 min-h-[calc(100vh-116px)] w-screen -translate-x-1/2 -my-10">
        <div className="mx-auto max-w-5xl space-y-16 px-6 py-12 lg:px-10">
          <DashboardSections
            workspaceId={workspaceId}
            lastVisitedAt={lastVisitedAt}
            isWorkspaceLoading={isWorkspaceLoading}
          />
        </div>
      </main>
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
  const { decisions, contextItems, needsYouItems, delta, isLoading, error } =
    useDashboardData(workspaceId, lastVisitedAt)

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
      <p className="text-sm" style={{ color: '#b06863' }}>
        Failed to load dashboard: {error}
      </p>
    )
  }

  return (
    <>
      <Headline delta={delta} lastVisitedAt={lastVisitedAt} />
      <RecentDecisions data={decisions} lastVisitedAt={lastVisitedAt} />
      <ActiveContext items={contextItems} lastVisitedAt={lastVisitedAt} />
      <NeedsYou items={needsYouItems} lastVisitedAt={lastVisitedAt} />
    </>
  )
}
