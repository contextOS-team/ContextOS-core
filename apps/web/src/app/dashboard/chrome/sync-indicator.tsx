'use client'

import { useEffect, useRef } from 'react'
import type { SyncState } from './use-sync-state'

interface SyncIndicatorProps {
  state: SyncState
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

export function SyncIndicator({ state }: SyncIndicatorProps) {
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
      <span
        className="min-w-[104px] text-right"
        aria-label="sync status unknown"
        aria-live="polite"
      >
        <span
          data-testid="sync-indicator-label"
          className="block text-[12px] font-medium leading-none text-muted-foreground"
          style={{
            fontFamily: 'var(--font-geist-sans)',
            fontVariantNumeric: 'tabular-nums',
            fontWeight: 450,
          }}
        >
          updated —
        </span>
      </span>
    )
  }

  if (state.kind === 'syncing') {
    const progressPercent = state.progress == null ? 0 : Math.round(state.progress * 100)

    return (
      <span
        className="min-w-[132px] text-right"
        aria-label={`syncing ${state.provider}${state.progress == null ? '' : ` ${progressPercent}%`}`}
        aria-live="polite"
      >
        <span
          ref={labelRef}
          data-testid="sync-indicator-label"
          className="block text-[12px] font-medium leading-none text-foreground"
          style={{
            fontFamily: 'var(--font-geist-sans)',
            fontVariantNumeric: 'tabular-nums',
            fontWeight: 450,
          }}
        >
          syncing {state.provider}
          {state.progress == null ? '' : ` · ${progressPercent}%`}
        </span>
        <span className="mt-1 block h-px w-full bg-border/40" aria-hidden="true">
          <span
            data-testid="sync-progress-fill"
            className="block h-px bg-primary/60"
            style={{
              width: `${progressPercent}%`,
              // Real progress ticks should step, not interpolate and imply fake movement.
              transition: 'none',
            }}
          />
        </span>
      </span>
    )
  }

  if (state.kind === 'error') {
    return (
      <span
        className="min-w-[132px] text-right"
        aria-label={`${state.provider} sync paused`}
        aria-live="polite"
        title={state.message}
      >
        <span
          data-testid="sync-indicator-label"
          className="block text-[12px] font-medium leading-none text-destructive"
          style={{
            fontFamily: 'var(--font-geist-sans)',
            fontVariantNumeric: 'tabular-nums',
            fontWeight: 450,
          }}
        >
          {state.provider} sync paused
        </span>
      </span>
    )
  }

  return (
    <span
      className="min-w-[104px] text-right"
      aria-label={`updated ${formatShortRelativeSyncTime(state.lastUpdatedAt)}`}
      aria-live="polite"
    >
      <span
        ref={labelRef}
        data-testid="sync-indicator-label"
        className="block text-[12px] font-medium leading-none text-muted-foreground"
        style={{
          fontFamily: 'var(--font-geist-sans)',
          fontVariantNumeric: 'tabular-nums',
          fontWeight: 450,
        }}
      >
        updated {formatShortRelativeSyncTime(state.lastUpdatedAt)}
      </span>
    </span>
  )
}
