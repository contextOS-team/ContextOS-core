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
  getDashboardResurfaced,
  getDashboardWeeklySummary,
  getDashboardSprint,
  type IntegrationStatusResponse,
  type AttentionItem,
  type ResurfacedItem,
  type DaySummary,
  type SprintData,
} from '@/lib/api'
import { Skeleton } from '@/components/ui/skeleton'
import Link from 'next/link'
import { fetchContextPages, type ContextPageRow, STATUS_COLORS } from '@/lib/context-feed'
import { NeedsAttention } from './widgets/needs-attention'
import { Resurfaced } from './widgets/resurfaced'
import { ThisWeek } from './widgets/this-week'
import { SprintBadge } from './widgets/sprint-badge'
import { IntegrationDots } from './widgets/integration-dots'

function getGreeting(): string {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

export default function DashboardPage() {
  const router = useRouter()
  const [firstName, setFirstName] = useState('')
  const [statuses, setStatuses] = useState<IntegrationStatusResponse | null>(null)
  const [attentionItems, setAttentionItems] = useState<AttentionItem[]>([])
  const [resurfacedItems, setResurfacedItems] = useState<ResurfacedItem[]>([])
  const [weeklySummary, setWeeklySummary] = useState<DaySummary[]>([])
  const [sprintData, setSprintData] = useState<SprintData | null>(null)
  const [recentPages, setRecentPages] = useState<ContextPageRow[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    setError(null)
    try {
      const results = await Promise.allSettled([
        getDashboardAttention(),
        getDashboardResurfaced(),
        getDashboardWeeklySummary(),
        getDashboardSprint(),
        getIntegrationStatus(),
        fetchContextPages(),
        createClient().auth.getUser(),
      ])

      const attention = results[0].status === 'fulfilled' ? results[0].value : []
      const resurfaced = results[1].status === 'fulfilled' ? results[1].value : []
      const weekly = results[2].status === 'fulfilled' ? results[2].value : []
      const sprint = results[3].status === 'fulfilled' ? results[3].value : null
      const integrations = results[4].status === 'fulfilled' ? results[4].value : null
      const pages = results[5].status === 'fulfilled' ? results[5].value : []
      const userRes = results[6].status === 'fulfilled' ? results[6].value : null

      const u = userRes?.data?.user
      if (u) {
        const fullName = u.user_metadata?.full_name as string | undefined
        setFirstName(fullName ? fullName.split(' ')[0] : (u.email?.split('@')[0] ?? ''))
      }

      setAttentionItems(attention)
      setResurfacedItems(resurfaced)
      setWeeklySummary(weekly)
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
      <div className="space-y-6 animate-fade-in-up">
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

  return (
    <div className="space-y-6 animate-fade-in-up">
      {/* Header: greeting + sprint badge */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {getGreeting()}{firstName ? `, ${firstName}` : ''}
        </p>
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

      {/* Intelligence widgets */}
      <NeedsAttention items={attentionItems} />
      <Resurfaced items={resurfacedItems} />
      <ThisWeek days={weeklySummary} />

      {/* Recent Context (condensed) */}
      {recentPages.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="section-label">Recent Context</h3>
            <Link
              href="/dashboard/context"
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              View all
            </Link>
          </div>
          <div className="rounded-xl border bg-card overflow-hidden divide-y divide-border">
            {recentPages.map((page) => {
              const colors = STATUS_COLORS[page.status] ?? STATUS_COLORS.draft
              return (
                <button
                  key={page.id}
                  onClick={() => router.push(`/dashboard/context/${page.id}`)}
                  className={`w-full text-left px-4 py-3 transition-colors duration-150 hover:bg-muted/40 border-l-2 ${colors.border}`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium text-foreground truncate">
                      {page.title}
                    </span>
                    <span className={`shrink-0 h-1.5 w-1.5 rounded-full ${colors.dot}`} />
                  </div>
                  <div className="flex items-center gap-3 mt-0.5">
                    <span className="text-xs font-mono text-muted-foreground">
                      {page.ticket_identifier}
                    </span>
                    <span className="text-xs font-mono text-muted-foreground">
                      {formatRelativeTime(page.updated_at)}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {page.sources?.length ?? 0} sources
                    </span>
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* Integration dots footer */}
      {statuses && <IntegrationDots statuses={statuses} />}
    </div>
  )
}
