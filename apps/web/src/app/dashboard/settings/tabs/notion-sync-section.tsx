'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  resyncNotion,
  getNotionSyncStatus,
  type ProviderStatus,
} from '@/lib/api'
import { displayName, formatRelativeTime } from '@/lib/utils'
import { NotionLogo } from '@/components/icons/brand-logos'
import { IntegrationCard } from '../../integrations/integration-card'
import { computeSyncState } from '@/lib/sync-progress'

interface NotionSyncSectionProps {
  notionStatus: ProviderStatus
  isPageLoading: boolean
  fetchStatuses: () => Promise<void>
  onConnect: () => void
  onDisconnect: () => Promise<void>
  setError: (error: string | null) => void
}

export function NotionSyncSection({
  notionStatus,
  isPageLoading,
  fetchStatuses,
  onConnect,
  onDisconnect,
  setError,
}: NotionSyncSectionProps) {
  const [isResyncing, setIsResyncing] = useState(false)
  const [syncProgress, setSyncProgress] = useState<number | null>(null)
  const [syncTotal, setSyncTotal] = useState<number | null>(null)
  const cancelledRef = useRef(false)
  const isResyncingRef = useRef(false)

  const pollSyncProgress = useCallback(async () => {
    cancelledRef.current = false
    let settled = false
    for (let i = 0; i < 180; i++) {
      if (cancelledRef.current) return
      await new Promise((r) => setTimeout(r, 2000))
      if (cancelledRef.current) return
      try {
        const s = await getNotionSyncStatus()
        if (cancelledRef.current) return
        setSyncProgress(s.sync_progress ?? s.pages_count)
        setSyncTotal(s.sync_total ?? null)
        if (s.sync_status === 'error') {
          setError('Notion sync failed. You can try again.')
          settled = true
          break
        }
        if (s.sync_status !== 'syncing') {
          settled = true
          break
        }

        // Detect stale sync -- if started_at is missing or older than 11 min
        const elapsed = s.sync_started_at
          ? Date.now() - new Date(s.sync_started_at).getTime()
          : Infinity
        if (elapsed > 11 * 60 * 1000) {
          setError('Notion sync appears stuck. Try re-syncing.')
          settled = true
          break
        }
      } catch {
        // Network error -- keep polling, backend may recover
      }
    }
    if (cancelledRef.current) return
    if (!settled) {
      setError('Notion sync is taking too long. Try re-syncing.')
    }
    await fetchStatuses()
    setIsResyncing(false)
    setSyncProgress(null)
    setSyncTotal(null)
  }, [fetchStatuses, setError])

  // Keep ref in sync with state for use in mount-only effect
  isResyncingRef.current = isResyncing

  // Resume Notion sync polling on mount if a sync is already in progress
  useEffect(() => {
    if (isPageLoading || isResyncingRef.current) return
    let cancelled = false
    getNotionSyncStatus()
      .then((s) => {
        if (cancelled) return
        if (s.sync_status === 'syncing') {
          // Check if sync is stale before resuming poll.
          // Missing sync_started_at = legacy sync, treat as stale.
          const elapsed = s.sync_started_at
            ? Date.now() - new Date(s.sync_started_at).getTime()
            : Infinity
          if (elapsed > 11 * 60 * 1000) {
            setError('Notion sync appears stuck. Try re-syncing.')
            return
          }
          setIsResyncing(true)
          setSyncProgress(s.sync_progress ?? 0)
          setSyncTotal(s.sync_total ?? null)
          pollSyncProgress()
        } else if (s.sync_status === 'error' && !s.pages_count) {
          // Only show error banner on mount if no pages were ever synced.
          // If pages exist, a previous sync succeeded and the user can
          // re-sync from the card — no need for an alarming top-level error.
          setError('Notion sync failed. You can try re-syncing.')
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
      cancelledRef.current = true
    }
    // isResyncing is read via ref to avoid re-triggering during sync.
    // pollSyncProgress and fetchStatuses are stable via useCallback.
  }, [isPageLoading, fetchStatuses, pollSyncProgress, setError])

  const handleResyncNotion = async () => {
    setError(null)
    setIsResyncing(true)
    setSyncProgress(0)
    try {
      try {
        await resyncNotion()
      } catch (err) {
        // Backend returns 409 when resetting a stale sync -- retry once
        if (err instanceof Error && err.message.includes('409')) {
          await new Promise((r) => setTimeout(r, 1000))
          await resyncNotion()
        } else {
          throw err
        }
      }
      await pollSyncProgress()
    } catch {
      setError('Failed to start Notion re-sync.')
      setIsResyncing(false)
      setSyncProgress(null)
      setSyncTotal(null)
    }
  }

  const notion = notionStatus
  const ns = computeSyncState({ isResyncing, syncProgress, syncTotal })

  return (
    <IntegrationCard
      name="Notion"
      icon={<NotionLogo width={20} height={20} className="text-foreground" />}
      status={notion.status}
      externalName={displayName(notion.external_name)}
      connectedAt={notion.connected_at}
      onConnect={onConnect}
      onDisconnect={onDisconnect}
      syncing={ns.syncing}
      syncPercent={ns.percent}
      syncLabel={ns.label}
    >
      <div className="space-y-3">
        {ns.syncing ? (
          <>
            {/* Phase label + counter */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Loader2 className="h-3.5 w-3.5 text-primary animate-spin" />
                <span className="text-sm font-medium text-foreground">
                  {ns.phaseLabel}
                </span>
              </div>
              {ns.hasTotal && (
                <span className="text-xs font-mono text-muted-foreground">
                  {ns.progress}/{syncTotal}
                </span>
              )}
            </div>

            {/* Progress bar (only during phase 2 when we have a total) */}
            {ns.percent != null && (
              <div
                className="h-1.5 w-full rounded-full bg-muted overflow-hidden"
                role="progressbar"
                aria-valuenow={ns.percent}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Notion sync progress"
              >
                <div
                  className="h-full rounded-full bg-primary transition-all duration-700 ease-out relative overflow-hidden"
                  style={{ width: `${Math.max(ns.percent, 2)}%` }}
                >
                  <div className="absolute inset-0 animate-[sync-shimmer_1.5s_ease-in-out_infinite] bg-gradient-to-r from-transparent via-white/40 to-transparent" />
                </div>
              </div>
            )}

            {/* Reassurance */}
            <p className="text-xs text-muted-foreground/70">
              Syncing continues in the background -- you can leave this page.
            </p>
          </>
        ) : (
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              {notion.pages_synced != null && notion.pages_synced > 0
                ? `${notion.pages_synced} pages synced${notion.last_sync_at ? ` \u00b7 ${formatRelativeTime(notion.last_sync_at)}` : ''}`
                : 'No pages synced yet'}
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={handleResyncNotion}
              className="text-[13px]"
            >
              Re-sync
            </Button>
          </div>
        )}
      </div>
    </IntegrationCard>
  )
}
