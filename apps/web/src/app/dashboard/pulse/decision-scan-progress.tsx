'use client'

import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, Loader2, PauseCircle, Search, Timer } from 'lucide-react'
import { motion, useReducedMotion } from 'motion/react'
import type { MissedDecisionScanStatus } from '@/lib/api'

const TIMING = {
  cardAppear: 0,
  providerRow: 120,
  progressFill: 220,
  candidateCount: 360,
  completionSettle: 520,
}

const CARD = {
  offsetY: 8,
  spring: { type: 'spring' as const, stiffness: 340, damping: 32 },
}

const PROVIDER_ROW = {
  offsetY: 4,
  spring: { type: 'spring' as const, stiffness: 380, damping: 34 },
}

const PROGRESS_BAR = {
  heightClass: 'h-1.5',
  spring: { type: 'spring' as const, stiffness: 260, damping: 30 },
}

const COUNT = {
  offsetY: 3,
  spring: { type: 'spring' as const, stiffness: 420, damping: 30 },
}

type SourceMeta = {
  label: string
  unit: string
  queued: string
  running: string
}

const SOURCE_META: Record<MissedDecisionScanStatus['source_type'], SourceMeta> = {
  slack_message: {
    label: 'Slack',
    unit: 'messages',
    queued: 'Waiting to scan Slack for missed decisions',
    running: 'Scanning Slack for missed decisions',
  },
  notion_page: {
    label: 'Notion',
    unit: 'pages',
    queued: 'Waiting to scan Notion for missed decisions',
    running: 'Scanning Notion for missed decisions',
  },
  telegram_message: {
    label: 'Telegram',
    unit: 'messages',
    queued: 'Waiting to scan Telegram for missed decisions',
    running: 'Scanning Telegram for missed decisions',
  },
  fathom_transcript: {
    label: 'Fathom',
    unit: 'transcripts',
    queued: 'Waiting to scan Fathom for missed decisions',
    running: 'Scanning Fathom for missed decisions',
  },
}

interface DecisionScanProgressProps {
  scans: MissedDecisionScanStatus[]
}

function clampProgress(value: number | null): number {
  if (value === null || Number.isNaN(value)) return 0
  return Math.max(0, Math.min(100, value))
}

function primaryScan(scans: MissedDecisionScanStatus[]): MissedDecisionScanStatus | null {
  return (
    scans.find((scan) => scan.status === 'running')
    ?? scans.find((scan) => scan.status === 'queued')
    ?? scans.find((scan) => scan.status === 'failed')
    ?? scans[0]
    ?? null
  )
}

function sourceMeta(scan: MissedDecisionScanStatus): SourceMeta {
  return SOURCE_META[scan.source_type]
}

function headingFor(scan: MissedDecisionScanStatus): string {
  const meta = sourceMeta(scan)
  if (scan.status === 'queued') return meta.queued
  if (scan.status === 'running') return meta.running
  if (scan.status === 'failed') return 'Scan paused'
  if (scan.candidates_created > 0) {
    const suffix = scan.candidates_created === 1 ? '' : 's'
    return `Found ${scan.candidates_created} candidate${suffix}`
  }
  return 'No missed decisions in this scan'
}

function pluralize(count: number, singular: string): string {
  return `${count} ${singular}${count === 1 ? '' : 's'}`
}

function candidateBreakdown(scan: MissedDecisionScanStatus): string {
  const parts: string[] = []
  if (scan.candidates_created > 0) {
    parts.push(pluralize(scan.candidates_created, 'candidate') + ' found')
  }
  if (scan.review_candidates > 0 || scan.candidates_created === 0) {
    parts.push(`${scan.review_candidates} need review`)
  }
  if (scan.auto_saved > 0) {
    parts.push(`${scan.auto_saved} auto-saved`)
  }
  if (scan.suppressed > 0) {
    parts.push(`${scan.suppressed} suppressed`)
  }
  return parts.join(' · ')
}

function detailFor(scan: MissedDecisionScanStatus): string {
  const meta = sourceMeta(scan)
  if (scan.status === 'failed') {
    return scan.error_message?.slice(0, 120) || 'ContextOS will retry from the last safe checkpoint.'
  }
  if (scan.candidates_created > 0) {
    return candidateBreakdown(scan)
  }
  if (scan.sources_total && scan.sources_total > 0) {
    const checked = `${scan.sources_scanned} of ${scan.sources_total} ${meta.unit} checked`
    return `${checked} · ${candidateBreakdown(scan)}`
  }
  if (scan.status === 'queued') return `${meta.label} is next in the scanner queue`
  if (scan.status === 'running') return `Checking ${meta.label} sources for missed decisions`
  return `${meta.label} scan complete`
}

function statusIcon(scan: MissedDecisionScanStatus) {
  if (scan.status === 'queued') return Timer
  if (scan.status === 'running') return Loader2
  if (scan.status === 'failed') return PauseCircle
  if (scan.candidates_created > 0) return Search
  return CheckCircle2
}

export function DecisionScanProgress({ scans }: DecisionScanProgressProps) {
  const reduceMotion = useReducedMotion()
  const scan = useMemo(() => primaryScan(scans), [scans])
  const [stage, setStage] = useState(0)
  const scanIdentityKey = scan?.id ?? 'empty'

  useEffect(() => {
    if (!scan) return
    if (reduceMotion) {
      setStage(5)
      return
    }

    setStage(0)
    const timers = [
      window.setTimeout(() => setStage(1), TIMING.cardAppear),
      window.setTimeout(() => setStage(2), TIMING.providerRow),
      window.setTimeout(() => setStage(3), TIMING.progressFill),
      window.setTimeout(() => setStage(4), TIMING.candidateCount),
      window.setTimeout(() => setStage(5), TIMING.completionSettle),
    ]

    return () => {
      timers.forEach(window.clearTimeout)
    }
  }, [scanIdentityKey, reduceMotion])

  if (!scan) return null

  const Icon = statusIcon(scan)
  const progress = clampProgress(scan.progress_percent)
  const hasDeterminateProgress = scan.sources_total !== null && scan.sources_total > 0
  const isRunning = scan.status === 'running'

  return (
    <motion.section
      className="pulse-card overflow-hidden px-4 py-4"
      initial={{ opacity: 0, y: CARD.offsetY }}
      animate={{
        opacity: stage >= 1 ? 1 : 0,
        y: stage >= 1 ? 0 : CARD.offsetY,
      }}
      transition={reduceMotion ? { duration: 0 } : CARD.spring}
      aria-label="Missed-decision scan progress"
    >
      <motion.div
        className="flex items-start gap-3"
        initial={{ opacity: 0, y: PROVIDER_ROW.offsetY }}
        animate={{
          opacity: stage >= 2 ? 1 : 0,
          y: stage >= 2 ? 0 : PROVIDER_ROW.offsetY,
        }}
        transition={reduceMotion ? { duration: 0 } : PROVIDER_ROW.spring}
      >
        <span className="mt-0.5 inline-flex size-8 shrink-0 items-center justify-center rounded-md bg-white/[0.055] text-[var(--pulse-foreground)]">
          <Icon
            className={`size-4 ${isRunning && !reduceMotion ? 'animate-spin' : ''}`}
            aria-hidden="true"
          />
        </span>
        <div className="min-w-0 flex-1 space-y-3">
          <div className="space-y-1">
            <h2 className="pulse-section-label">{headingFor(scan)}</h2>
            <motion.p
              className="text-sm leading-5 text-[var(--pulse-muted)]"
              initial={{ opacity: 0, y: COUNT.offsetY }}
              animate={{
                opacity: stage >= 4 ? 1 : 0,
                y: stage >= 4 ? 0 : COUNT.offsetY,
              }}
              transition={reduceMotion ? { duration: 0 } : COUNT.spring}
            >
              {detailFor(scan)}
            </motion.p>
          </div>

          <div
            className={`relative w-full overflow-hidden rounded-full bg-white/[0.06] ${PROGRESS_BAR.heightClass}`}
            role={hasDeterminateProgress ? 'progressbar' : undefined}
            aria-valuenow={hasDeterminateProgress ? progress : undefined}
            aria-valuemin={hasDeterminateProgress ? 0 : undefined}
            aria-valuemax={hasDeterminateProgress ? 100 : undefined}
          >
            {hasDeterminateProgress ? (
              <motion.div
                className="h-full rounded-full bg-[var(--pulse-attention)]"
                initial={{ width: '0%' }}
                animate={{ width: stage >= 3 ? `${progress}%` : '0%' }}
                transition={reduceMotion ? { duration: 0 } : PROGRESS_BAR.spring}
              />
            ) : (
              <div className="absolute inset-0 animate-[sync-shimmer_1.6s_ease-in-out_infinite] bg-gradient-to-r from-transparent via-white/30 to-transparent" />
            )}
          </div>
        </div>
      </motion.div>
    </motion.section>
  )
}
