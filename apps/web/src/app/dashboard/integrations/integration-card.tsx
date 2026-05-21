'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { displayName, formatRelativeTime } from '@/lib/utils'
import { ChevronDown, Loader2 } from 'lucide-react'

type IntegrationStatus = 'connected' | 'disconnected' | 'error'

interface IntegrationCardProps {
  name: string
  icon: React.ReactNode
  status: IntegrationStatus
  externalName?: string | null
  connectedAt?: string | null
  onConnect: () => void | Promise<void>
  onDisconnect: () => void | Promise<void>
  children?: React.ReactNode
  connectForm?: React.ReactNode
  /** When true, the connect button is disabled */
  disabled?: boolean
  /** Shown below the card name when disabled */
  disabledReason?: string
  /** Whether a background sync is in progress. Controls header dot pulse and label. */
  syncing?: boolean
  /** Sync progress 0–100. Shown as compact bar in header when collapsed. */
  syncPercent?: number | null
  /** Short label for sync state shown in header, e.g. "80/354 pages" */
  syncLabel?: string | null
}

function StatusIndicator({ status, syncing }: { status: IntegrationStatus; syncing?: boolean }) {
  if (syncing) {
    return (
      <span className="shrink-0 h-1.5 w-1.5 rounded-full bg-primary animate-[sync-pulse_1.5s_ease-in-out_infinite]" />
    )
  }
  if (status === 'connected') {
    return (
      <span className="shrink-0 h-1.5 w-1.5 rounded-full bg-emerald-500" />
    )
  }
  if (status === 'error') {
    return (
      <span className="shrink-0 h-1.5 w-1.5 rounded-full bg-red-500" />
    )
  }
  return (
    <span className="shrink-0 h-1.5 w-1.5 rounded-full border border-muted-foreground/30" />
  )
}

/** Clamp to [0, 100] to prevent overflow from stale data or race conditions. */
function clampPercent(v: number): number {
  return Math.max(0, Math.min(100, v))
}

export function IntegrationCard({
  name,
  icon,
  status,
  externalName,
  connectedAt,
  onConnect,
  onDisconnect,
  children,
  connectForm,
  disabled,
  disabledReason,
  syncing,
  syncPercent,
  syncLabel,
}: IntegrationCardProps) {
  const [isLoading, setIsLoading] = useState(false)
  const [isExpanded, setIsExpanded] = useState(false)
  const [showConnectForm, setShowConnectForm] = useState(false)
  const [showDisconnect, setShowDisconnect] = useState(false)

  const hasSyncBar = syncPercent != null
  const clampedPercent = hasSyncBar ? clampPercent(syncPercent) : 0

  async function handleConnect() {
    if (connectForm) {
      setShowConnectForm(true)
      return
    }
    setIsLoading(true)
    try {
      await onConnect()
    } finally {
      setIsLoading(false)
    }
  }

  async function handleDisconnect() {
    setShowDisconnect(false)
    setIsLoading(true)
    try {
      await onDisconnect()
    } finally {
      setIsLoading(false)
    }
  }

  const displayedName = displayName(externalName)

  return (
    <Card className="dashboard-panel dashboard-panel--interactive gap-0 overflow-hidden border-0 py-0 shadow-none group">
      <div className="flex flex-row items-center justify-between gap-3 px-5 pt-5 pb-2">
        <div className="flex items-center gap-3 min-w-0">
          <div className="shrink-0">
            {icon}
          </div>
          <div className="flex items-center gap-2 min-w-0">
            <h3 className="text-[15px] font-semibold tracking-[-0.01em] text-foreground">{name}</h3>
            <StatusIndicator status={status} syncing={syncing} />
          </div>
        </div>
        {/* Sync label in header — visible even when collapsed */}
        {syncLabel && (
          <span className="text-xs font-medium text-primary shrink-0">
            {syncLabel}
          </span>
        )}
        {/* Connection info inline with header (hidden while syncing) */}
        {!syncLabel && status === 'connected' && (displayedName || connectedAt) && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground shrink-0">
            {displayedName && (
              <span className="font-medium text-foreground/70 truncate max-w-[120px]">
                {displayedName}
              </span>
            )}
            {connectedAt && (
              <span className="font-mono text-[11px] text-muted-foreground/60">
                {formatRelativeTime(connectedAt)}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Compact sync progress bar — only when collapsed, suppressed when expanded to avoid duplication */}
      {hasSyncBar && !isExpanded && (
        <div className="px-5 pb-1">
          <div
            className="h-1 w-full rounded-full bg-muted overflow-hidden"
            role="progressbar"
            aria-valuenow={clampedPercent}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`${name} sync progress`}
          >
            <div
              className="h-full rounded-full bg-primary transition-[width] duration-700 ease-out relative overflow-hidden"
              style={{ width: `${Math.max(clampedPercent, 2)}%` }}
            >
              <div className="absolute inset-0 animate-[sync-shimmer_1.5s_ease-in-out_infinite] bg-gradient-to-r from-transparent via-white/40 to-transparent" />
            </div>
          </div>
        </div>
      )}

      <CardContent className="px-5 pb-4 pt-0">
        {/* Actions */}
        <div className={`flex items-center gap-2 ${showConnectForm ? '' : 'h-8'}`}>
          {status === 'connected' ? (
            <>
              {children && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsExpanded(!isExpanded)}
                  className="gap-1.5 text-[13px]"
                >
                  {isExpanded ? 'Hide settings' : 'Settings'}
                  <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`} />
                </Button>
              )}
              <AlertDialog open={showDisconnect} onOpenChange={setShowDisconnect}>
                <button
                  onClick={() => setShowDisconnect(true)}
                  disabled={isLoading}
                  className="text-[12px] text-muted-foreground hover:text-red-500 dark:hover:text-red-400 transition-colors duration-150 disabled:opacity-50 ml-1"
                >
                  {isLoading ? (
                    <span className="flex items-center gap-1.5">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      Disconnecting
                    </span>
                  ) : 'Disconnect'}
                </button>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Disconnect {name}?</AlertDialogTitle>
                    <AlertDialogDescription>
                      This will stop syncing data from {name}. Existing data will be kept.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={handleDisconnect}
                      className="bg-destructive text-white hover:bg-destructive/90"
                    >
                      Disconnect
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </>
          ) : (
            !showConnectForm && (
              disabled && disabledReason ? (
                <p className="text-[12px] text-muted-foreground/60">{disabledReason}</p>
              ) : (
                <Button
                  size="sm"
                  onClick={handleConnect}
                  disabled={isLoading}
                  className="text-[13px]"
                >
                  {isLoading ? (
                    <span className="flex items-center gap-1.5">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Connecting
                    </span>
                  ) : 'Connect'}
                </Button>
              )
            )
          )}
        </div>

        {/* Inline connect form */}
        {connectForm && status !== 'connected' && showConnectForm && (
          <div className="dashboard-panel mt-4 p-4">
            {connectForm}
          </div>
        )}
      </CardContent>

      {/* Expandable content */}
      {children && status === 'connected' && isExpanded && (
        <div className="border-t border-white/[0.06] bg-white/[0.025] px-5 py-5">{children}</div>
      )}
    </Card>
  )
}
