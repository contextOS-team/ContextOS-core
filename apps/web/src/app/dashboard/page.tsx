'use client'

import { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { AlertCircle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { createClient } from '@/lib/supabase/client'
import { formatRelativeTime } from '@/lib/utils'
import {
  getIntegrationStatus,
  getDashboardAttention,
  getDashboardWeeklySummary,
  getDashboardSprint,
  fetchMyWorkGraph,
  type IntegrationStatusResponse,
  type AttentionItem,
  type DaySummary,
  type SprintData,
} from '@/lib/api'
import type { LensGraphResponse } from '@/components/graph/types'
import { Skeleton } from '@/components/ui/skeleton'
import Link from 'next/link'
import { fetchContextPages, type ContextPageRow, STATUS_COLORS } from '@/lib/context-feed'
import { NeedsAttention } from './widgets/needs-attention'
import { ThisWeek } from './widgets/this-week'
import { SprintBadge } from './widgets/sprint-badge'
import { IntegrationDots } from './widgets/integration-dots'
import { EmptyState } from './widgets/empty-state'
import { ActivityFeedMini } from './widgets/activity-feed-mini'
import { GraphThumbnail } from './widgets/graph-thumbnail'
import { RecentDecisions } from './widgets/recent-decisions'

function getGreeting(): string {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

function getSummaryLine(
  attentionCount: number,
  activeDayCount: number,
): string | null {
  const parts: string[] = []
  if (attentionCount > 0)
    parts.push(`${attentionCount} item${attentionCount === 1 ? '' : 's'} need${attentionCount === 1 ? 's' : ''} attention`)
  if (activeDayCount > 0)
    parts.push(`${activeDayCount} active day${activeDayCount === 1 ? '' : 's'} this week`)
  if (parts.length === 0) return null
  return parts.join(' · ')
}

export default function DashboardPage() {
  const router = useRouter()
  const [userFullName, setUserFullName] = useState('')
  const firstName = userFullName ? userFullName.split(' ')[0] : ''
  const [statuses, setStatuses] = useState<IntegrationStatusResponse | null>(null)
  const [attentionItems, setAttentionItems] = useState<AttentionItem[]>([])
  const [weeklySummary, setWeeklySummary] = useState<DaySummary[]>([])
  const [graphData, setGraphData] = useState<LensGraphResponse | null>(null)
  const [sprintData, setSprintData] = useState<SprintData | null>(null)
  const [recentPages, setRecentPages] = useState<ContextPageRow[]>([])
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    setError(null)
    try {
      // Chain user → workspace as one promise so it runs parallel with the rest
      const supabase = createClient()
      const userAndWorkspace = supabase.auth.getUser().then(async (res) => {
        const u = res.data?.user
        if (!u) return { user: null, wsId: null }
        const { data: m } = await supabase
          .from('workspace_members')
          .select('workspace_id')
          .eq('user_id', u.id)
          .single()
        return { user: u, wsId: m?.workspace_id ?? null }
      })

      const results = await Promise.allSettled([
        getDashboardAttention(),
        getDashboardWeeklySummary(),
        getDashboardSprint(),
        getIntegrationStatus(),
        fetchContextPages(),
        userAndWorkspace,
        fetchMyWorkGraph(),
      ])

      const attention = results[0].status === 'fulfilled' ? results[0].value : []
      const weekly = results[1].status === 'fulfilled' ? results[1].value : []
      const sprint = results[2].status === 'fulfilled' ? results[2].value : null
      const integrations = results[3].status === 'fulfilled' ? results[3].value : null
      const pages = results[4].status === 'fulfilled' ? results[4].value : []
      const uw = results[5].status === 'fulfilled' ? results[5].value : null
      const graph = results[6].status === 'fulfilled' ? results[6].value : null

      if (uw?.user) {
        const fullName = uw.user.user_metadata?.full_name as string | undefined
        setUserFullName(fullName ?? uw.user.email ?? '')
        if (uw.wsId) setWorkspaceId(uw.wsId)
      }

      setAttentionItems(attention)
      setWeeklySummary(weekly)
      setGraphData(graph)
      setSprintData(sprint)
      setStatuses(integrations)
      setRecentPages((pages as ContextPageRow[]).slice(0, 5))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard data')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  if (isLoading) {
    return (
      <div className="space-y-6 stagger-children">
        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-4 w-32" />
        </div>
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={`sk-${i}`}>
            <Skeleton className="h-3 w-28 mb-3" />
            <div className="rounded-xl border border-border overflow-hidden divide-y divide-border">
              {Array.from({ length: 2 }).map((_, j) => (
                <div key={`sk-${i}-${j}`} className="px-4 py-3 space-y-1.5">
                  <Skeleton className="h-4 w-64" />
                  <Skeleton className="h-3 w-32" />
                </div>
              ))}
            </div>
          </div>
        ))}
        <div className="flex gap-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={`dot-${i}`} className="h-3 w-14" />
          ))}
        </div>
      </div>
    )
  }

  const widgetsEmpty =
    attentionItems.length === 0 &&
    weeklySummary.filter(d => d.activity_count > 0 || d.contexts_updated > 0 || d.prs_merged > 0).length === 0
  const hasGraphData = (graphData?.all_nodes?.length ?? 0) > 0
  const isTrulyEmpty = widgetsEmpty && recentPages.length === 0 && !hasGraphData && !workspaceId

  // Derive context page stats for the smart banner
  const errorPages = recentPages.filter(p => p.status === 'error' || p.status === 'stale')
  const healthyPages = recentPages.filter(p => p.status === 'ready')

  // Split pages into temporal groups
  const now = Date.now()
  const todayPages = recentPages.filter(p => now - new Date(p.updated_at).getTime() < 86_400_000)
  const olderPages = recentPages.filter(p => now - new Date(p.updated_at).getTime() >= 86_400_000)

  return (
    <div className="space-y-6 stagger-children">
      {/* Header: greeting with context-aware subtitle + sprint badge */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-lg font-semibold text-foreground" style={{ textWrap: 'balance' }}>
            {getGreeting()}{firstName ? `, ${firstName}` : ''}
          </p>
          {(() => {
            const activeDays = weeklySummary.filter(
              (d) => d.activity_count > 0 || d.contexts_updated > 0 || d.prs_merged > 0
            )
            const summary = getSummaryLine(attentionItems.length, activeDays.length)
            if (summary) {
              return <p className="text-sm text-muted-foreground mt-0.5 tabular-nums">{summary}</p>
            }
            // Context-aware subtitle when widgets are empty but pages exist
            if (widgetsEmpty && recentPages.length > 0) {
              if (errorPages.length > 0) {
                return (
                  <p className="text-sm text-muted-foreground mt-0.5">
                    {errorPages.length === 1
                      ? `${errorPages[0].ticket_identifier ?? 'One context'} needs attention`
                      : `${errorPages.length} contexts need attention`}
                    {healthyPages.length > 0 && ` · ${healthyPages.length} healthy`}
                  </p>
                )
              }
              return (
                <p className="text-sm text-muted-foreground mt-0.5">
                  {recentPages.length} context{recentPages.length === 1 ? '' : 's'} healthy
                </p>
              )
            }
            return null
          })()}
        </div>
        <SprintBadge sprint={sprintData} />
      </div>

      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-3 rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm animate-scale-in">
          <AlertCircle className="h-4 w-4 shrink-0 text-destructive" />
          <span className="flex-1 text-destructive">{error}</span>
          <Button variant="ghost" size="sm" onClick={loadData} className="h-7 gap-1.5 text-destructive hover:text-destructive">
            <RefreshCw className="h-3 w-3" />
            Retry
          </Button>
        </div>
      )}

      {/* Empty state for first-time users with no data */}
      {isTrulyEmpty ? (
        <EmptyState statuses={statuses} />
      ) : (
        <>
          {/* 2-col grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left column */}
            <div className="space-y-6">
              <NeedsAttention items={attentionItems} />
              <ThisWeek days={weeklySummary} />

              {/* Recent Context with temporal grouping */}
              {recentPages.length > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="section-label">Recent Context</h3>
                    <div className="flex items-center gap-3">
                      <Link
                        href="/dashboard/context/generate"
                        className="text-xs text-primary/70 hover:text-primary transition-colors"
                      >
                        Generate
                      </Link>
                      <Link
                        href="/dashboard/context"
                        className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                      >
                        View all
                      </Link>
                    </div>
                  </div>

                  {/* Today group */}
                  {todayPages.length > 0 && (
                    <>
                      {olderPages.length > 0 && (
                        <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/60 mb-1.5">Today</p>
                      )}
                      <div className="widget-card rounded-xl divide-y divide-border mb-3">
                        {todayPages.map((page) => (
                          <ContextRow key={page.id} page={page} onClick={() => router.push(`/dashboard/context/${page.id}`)} />
                        ))}
                      </div>
                    </>
                  )}

                  {/* Earlier group */}
                  {olderPages.length > 0 && (
                    <>
                      {todayPages.length > 0 && (
                        <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/60 mb-1.5">Earlier</p>
                      )}
                      <div className="widget-card rounded-xl divide-y divide-border">
                        {olderPages.map((page) => (
                          <ContextRow key={page.id} page={page} onClick={() => router.push(`/dashboard/context/${page.id}`)} />
                        ))}
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>

            {/* Right column */}
            <div className="space-y-6">
              <ActivityFeedMini workspaceId={workspaceId} />
              <GraphThumbnail data={graphData} userName={userFullName} />
              <RecentDecisions data={graphData} />
            </div>
          </div>

          {/* Integration dots footer - full width */}
          {statuses && <IntegrationDots statuses={statuses} />}
          <div className="border-t border-border/30 mt-2" />
        </>
      )}
    </div>
  )
}

function ContextRow({ page, onClick }: { page: ContextPageRow; onClick: () => void }) {
  const colors = STATUS_COLORS[page.status] ?? STATUS_COLORS.draft
  const isRecent = Date.now() - new Date(page.updated_at).getTime() < 86_400_000
  const displayTitle = page.title.replace(/^Context:\s*/i, '')
  const isError = page.status === 'error' || page.status === 'stale'

  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-4 py-3 active:scale-[0.96] transition-[transform,background-color] duration-150 hover:bg-muted/40 border-l-[3px] ${colors.border} ${isError ? 'bg-red-500/[0.03]' : ''}`}
    >
      <div className="flex items-center justify-between gap-3">
        <span className={`text-sm truncate ${isRecent ? 'font-medium text-foreground' : 'font-normal text-foreground/70'}`}>
          {displayTitle}
        </span>
        <span className={`shrink-0 h-2 w-2 rounded-full ${colors.dot}`} />
      </div>
      <div className="flex items-center gap-2 mt-0.5">
        {page.ticket_identifier && (
          <span className="text-xs font-mono text-muted-foreground">
            {page.ticket_identifier}
          </span>
        )}
        <span className="text-xs text-muted-foreground/50">·</span>
        <span className="text-xs text-muted-foreground">
          {formatRelativeTime(page.updated_at)}
        </span>
        <span className="text-xs text-muted-foreground/50">·</span>
        <span className={`text-xs ${isError ? 'text-orange-400' : 'text-muted-foreground'}`}>
          {page.sources?.length ?? 0} source{(page.sources?.length ?? 0) === 1 ? '' : 's'}
        </span>
        {isError && (
          <>
            <span className="text-xs text-muted-foreground/50">·</span>
            <span className="text-[10px] text-orange-400/70 uppercase tracking-wider">
              needs attention
            </span>
          </>
        )}
      </div>
    </button>
  )
}
