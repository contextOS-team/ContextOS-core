'use client'

import { useEffect, useRef } from 'react'
import type { SyncState } from './use-sync-state'

interface SyncIndicatorProps {
  state: SyncState
  onOpenDrawer: () => void
}

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export function formatShortRelativeSyncTime(date: Date, now: Date = new Date()): string {
  const diffMs = Math.max(0, now.getTime() - date.getTime())
  const diffMin = Math.floor(diffMs / 60_000)
  const diffHours = Math.floor(diffMin / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffDays > 0) return `${diffDays}d ago`
  if (diffHours > 0) return `${diffHours}h ago`
  return `${diffMin}m ago`
}

export function SyncIndicator({ state, onOpenDrawer }: SyncIndicatorProps) {
  const labelRef = useRef<HTMLSpanElement>(null)
  const previousProviderRef = useRef<string | null>(null)

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

  if (state.kind === 'unknown') {
    return (
      <button
        type="button"
        onClick={onOpenDrawer}
        className="w-[240px] rounded-md px-2 py-1 text-left transition-colors duration-160 hover:bg-white/[0.025]"
        aria-label="sync status unknown"
      >
        <span
          data-testid="sync-indicator-label"
          className="block text-[12px] font-medium"
          style={{
            color: '#6e6b66',
            fontFamily: 'var(--font-geist-sans)',
            fontVariantNumeric: 'tabular-nums',
            fontWeight: 450,
          }}
        >
          last synced —
        </span>
      </button>
    )
  }

  if (state.kind === 'syncing') {
    const progressPercent = state.progress == null ? 0 : Math.round(state.progress * 100)

    return (
      <button
        type="button"
        onClick={onOpenDrawer}
        className="w-[240px] rounded-md px-2 py-1 text-left transition-colors duration-160 hover:bg-white/[0.025]"
        aria-label={`syncing ${state.provider}${state.progress == null ? '' : ` ${progressPercent}%`}`}
      >
        <span
          ref={labelRef}
          data-testid="sync-indicator-label"
          className="block text-[12px] font-medium"
          style={{
            color: '#a8a59f',
            fontFamily: 'var(--font-geist-sans)',
            fontVariantNumeric: 'tabular-nums',
            fontWeight: 450,
          }}
        >
          syncing {state.provider}
          {state.progress == null ? '' : ` · ${progressPercent}%`}
        </span>
        <span className="mt-1 block h-px w-full bg-white/[0.04]">
          <span
            data-testid="sync-progress-fill"
            className="block h-px bg-white/[0.18]"
            style={{
              width: `${progressPercent}%`,
              // Real progress ticks should step, not interpolate and imply fake movement.
              transition: 'none',
            }}
          />
        </span>
      </button>
    )
  }

  if (state.kind === 'error') {
    return (
      <button
        type="button"
        onClick={onOpenDrawer}
        className="w-[240px] rounded-md px-2 py-1 text-left transition-colors duration-160 hover:bg-white/[0.025]"
        aria-label={`${state.provider} sync paused reconnect`}
        title={state.message}
      >
        <span
          data-testid="sync-indicator-label"
          className="block text-[12px] font-medium"
          style={{
            color: '#c4a050',
            fontFamily: 'var(--font-geist-sans)',
            fontVariantNumeric: 'tabular-nums',
            fontWeight: 450,
          }}
        >
          {state.provider} sync paused · <span className="underline-offset-2 hover:underline">reconnect</span>
        </span>
      </button>
    )
  }

  return (
    <button
      type="button"
      onClick={onOpenDrawer}
      className="w-[240px] rounded-md px-2 py-1 text-left transition-colors duration-160 hover:bg-white/[0.025]"
      aria-label={`last synced ${formatShortRelativeSyncTime(state.lastSyncedAt)}`}
    >
      <span
        ref={labelRef}
        data-testid="sync-indicator-label"
        className="block text-[12px] font-medium"
        style={{
          color: '#6e6b66',
          fontFamily: 'var(--font-geist-sans)',
          fontVariantNumeric: 'tabular-nums',
          fontWeight: 450,
        }}
      >
        last synced {formatShortRelativeSyncTime(state.lastSyncedAt)}
      </span>
    </button>
  )
}
