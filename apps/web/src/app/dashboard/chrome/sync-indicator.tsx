'use client'

import { useEffect, useId, useRef, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import {
  sourceSyncSummary,
  triggerStaleSourceSyncs,
  type SourceSyncProgress,
} from '../source-sync-actions'
import {
  formatProviderName,
  type ChromeSourceState,
  type SourceHealth,
  type SourceRow,
} from './source-sync-state'

interface SyncIndicatorProps {
  state: ChromeSourceState
  onSyncRequested?: () => void
}

type ManualSyncState = {
  status: 'idle' | 'syncing' | 'success' | 'error'
  message: string | null
  progress: number | null
}

const HEALTH_COPY: Record<SourceHealth, string> = {
  current: 'Current',
  needs_sync: 'Needs sync',
  syncing: 'Syncing',
  attention: 'Needs attention',
  live: 'Live',
  not_configured: 'Not configured',
}

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function formatSyncProgressLabel(provider: string): string {
  return `Syncing ${formatProviderName(provider)}`
}

function progressPercent(progress: number | null): number | null {
  return progress == null
    ? null
    : Math.max(0, Math.min(100, Math.round(progress * 100)))
}

function stateLabel(state: ChromeSourceState): string {
  switch (state.kind) {
    case 'checking':
      return 'Checking sources'
    case 'current':
      return 'Sources current'
    case 'needs_sync':
      return 'Needs sync'
    case 'attention':
      return 'Needs attention'
    case 'syncing':
      return formatSyncProgressLabel(state.provider)
  }
}

function stateClass(state: ChromeSourceState, manualSync: ManualSyncState): string {
  if (manualSync.status === 'syncing' || state.kind === 'syncing') {
    return ''
  }

  if (state.kind === 'current') return 'chrome-sync-status--fresh'
  if (state.kind === 'needs_sync') return 'chrome-sync-status--stale'
  if (state.kind === 'attention') return 'chrome-sync-status--error'
  return 'chrome-sync-status--unknown'
}

function stateAriaLabel(state: ChromeSourceState, manualSync: ManualSyncState): string {
  if (manualSync.status === 'syncing') {
    const percent = progressPercent(manualSync.progress)
    return `syncing sources${percent == null ? '' : ` ${percent}%`}`
  }

  switch (state.kind) {
    case 'checking':
      return 'checking workspace source status'
    case 'current':
      return 'workspace sources current'
    case 'needs_sync':
      return 'workspace sources need sync'
    case 'attention':
      return 'workspace sources need attention'
    case 'syncing': {
      const percent = progressPercent(state.progress)
      return `syncing ${state.provider}${percent == null ? '' : ` ${percent}%`}`
    }
  }
}

function SourceRowItem({ row }: { row: SourceRow }) {
  return (
    <div className="chrome-sync-source-row">
      <span className={`chrome-sync-source-dot chrome-sync-source-dot--${row.health}`} aria-hidden="true" />
      <span className="chrome-sync-source-main">
        <span className="chrome-sync-source-label">{row.label}</span>
        <span className="chrome-sync-source-detail">{row.detail}</span>
      </span>
      <span className="chrome-sync-source-health">
        {row.health === 'syncing' && row.progress != null
          ? `${progressPercent(row.progress)}%`
          : HEALTH_COPY[row.health]}
      </span>
    </div>
  )
}

function SyncProgress({
  label,
  progress,
}: {
  label: string
  progress: number | null
}) {
  const percent = progressPercent(progress)

  return (
    <>
      <span className="chrome-sync-label">
        <span>{label}</span>
        {percent != null && <span>{percent}%</span>}
      </span>
      <span
        className="chrome-sync-track"
        role="progressbar"
        aria-label={label}
        aria-valuemin={percent == null ? undefined : 0}
        aria-valuemax={percent == null ? undefined : 100}
        aria-valuenow={percent ?? undefined}
      >
        <span
          data-testid="sync-progress-fill"
          className={`chrome-sync-fill ${percent == null ? 'chrome-sync-fill--indeterminate' : ''}`}
          style={percent == null ? undefined : { width: `${percent}%` }}
        />
      </span>
    </>
  )
}

export function SyncIndicator({ state, onSyncRequested }: SyncIndicatorProps) {
  const menuId = useId()
  const rootRef = useRef<HTMLDivElement>(null)
  const labelRef = useRef<HTMLSpanElement>(null)
  const previousProviderRef = useRef<string | null>(null)
  const [open, setOpen] = useState(false)
  const [manualSync, setManualSync] = useState<ManualSyncState>({
    status: 'idle',
    message: null,
    progress: null,
  })

  const visibleSyncing = manualSync.status === 'syncing' || state.kind === 'syncing'
  const visibleLabel = manualSync.status === 'syncing'
    ? 'Syncing sources'
    : stateLabel(state)
  const visibleProgress = manualSync.status === 'syncing'
    ? manualSync.progress
    : state.kind === 'syncing' ? state.progress : null
  const sources = state.sources
  const canSync = state.kind === 'needs_sync'
    && manualSync.status !== 'syncing'
    && manualSync.status !== 'success'

  useEffect(() => {
    if (prefersReducedMotion()) return

    const interval = window.setInterval(() => {
      labelRef.current?.animate?.(
        [{ opacity: 1 }, { opacity: 0.6 }, { opacity: 1 }],
        { duration: 240, easing: 'ease-out' }
      )
    }, 60_000)

    return () => window.clearInterval(interval)
  }, [])

  useEffect(() => {
    if (state.kind !== 'syncing' || prefersReducedMotion()) return

    const previous = previousProviderRef.current
    previousProviderRef.current = state.provider

    if (previous && previous !== state.provider) {
      labelRef.current?.animate?.(
        [{ filter: 'blur(2px)' }, { filter: 'blur(0)' }],
        { duration: 180, easing: 'ease-out' }
      )
    }
  }, [state])

  useEffect(() => {
    if (manualSync.status !== 'syncing') return

    if (state.kind === 'syncing') {
      setManualSync({ status: 'idle', message: null, progress: null })
    } else if (state.kind === 'current') {
      setManualSync({ status: 'success', message: 'Sources current.', progress: 1 })
    } else if (state.kind === 'attention') {
      setManualSync({ status: 'error', message: state.message, progress: null })
    }
  }, [manualSync.status, state])

  useEffect(() => {
    if (!open) return

    function handlePointerDown(event: PointerEvent) {
      if (rootRef.current?.contains(event.target as Node)) return
      setOpen(false)
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }

    document.addEventListener('pointerdown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)

    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  async function handleSyncSources() {
    if (manualSync.status === 'syncing') return

    setOpen(true)
    setManualSync({
      status: 'syncing',
      message: 'Checking connected sources',
      progress: 0.08,
    })

    try {
      const { started } = await triggerStaleSourceSyncs((progress: SourceSyncProgress) => {
        setManualSync({
          status: 'syncing',
          message: progress.message,
          progress: progress.progress,
        })
      })

      if (started.length === 0) {
        setManualSync({
          status: 'success',
          message: sourceSyncSummary(started),
          progress: 1,
        })
        return
      }

      onSyncRequested?.()
      setManualSync({
        status: 'syncing',
        message: sourceSyncSummary(started),
        progress: null,
      })
    } catch (error) {
      setManualSync({
        status: 'error',
        message: error instanceof Error ? error.message : 'Could not start source sync.',
        progress: null,
      })
    }
  }

  return (
    <div ref={rootRef} className="chrome-sync-wrap">
      <button
        type="button"
        className={`chrome-sync-status ${visibleSyncing ? '' : 'chrome-sync-status--idle'} ${stateClass(state, manualSync)}`}
        aria-controls={open ? menuId : undefined}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label={stateAriaLabel(state, manualSync)}
        aria-live="polite"
        onClick={() => setOpen((current) => !current)}
      >
        {visibleSyncing ? (
          <SyncProgress
            label={visibleLabel}
            progress={visibleProgress}
          />
        ) : (
          <span
            ref={labelRef}
            data-testid="sync-indicator-label"
            className="chrome-sync-inline"
          >
            <span className="chrome-sync-dot" aria-hidden="true" />
            {visibleLabel}
          </span>
        )}
      </button>
      {open && (
        <div
          id={menuId}
          role="dialog"
          aria-label="Source sync status"
          className="chrome-sync-menu"
        >
          <div className="chrome-sync-menu-title">Sources</div>
          {sources.length > 0 ? (
            <div className="chrome-sync-source-list">
              {sources.map((row) => (
                <SourceRowItem key={row.provider} row={row} />
              ))}
            </div>
          ) : (
            <p className="chrome-sync-menu-empty">
              {state.kind === 'checking' ? 'Checking connected sources.' : 'No connected sources.'}
            </p>
          )}

          {(canSync || manualSync.status !== 'idle') && (
            <div className="chrome-sync-menu-footer">
              {manualSync.status === 'syncing' && (
                <div className="chrome-sync-menu-progress">
                  <SyncProgress
                    label={manualSync.message ?? 'Syncing sources'}
                    progress={manualSync.progress}
                  />
                </div>
              )}
              {manualSync.message && manualSync.status !== 'syncing' && (
                <p className={`chrome-sync-menu-message chrome-sync-menu-message--${manualSync.status}`}>
                  {manualSync.message}
                </p>
              )}
              {canSync && (
                <button
                  type="button"
                  className="chrome-sync-menu-action"
                  onClick={(event) => {
                    event.preventDefault()
                    void handleSyncSources()
                  }}
                >
                  <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                  Sync stale sources
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
