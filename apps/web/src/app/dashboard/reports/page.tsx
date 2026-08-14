'use client'

import { useEffect, useState } from 'react'
import { Skeleton } from '@/components/ui/skeleton'
import { getCoverageReport, type CoverageReport } from '@/lib/api'

const WINDOWS = [30, 60, 90] as const

const RESOLUTION_LABELS: Record<string, string> = {
  jira_updated: 'Jira updated',
  linear_updated: 'Linear updated',
  doc_updated: 'Doc updated',
  implementation_changed: 'Implementation changed',
  work_cancelled: 'Work cancelled',
  timeline_changed: 'Timeline changed',
  intentional_exception: 'Intentional exception',
  other: 'Other',
}

// Status colors (dataviz: reserved status palette, always paired with a label).
const SEGMENTS = [
  { key: 'aligned', label: 'Aligned', className: 'cov-seg--good' },
  { key: 'uncertain', label: 'Uncertain', className: 'cov-seg--warning' },
  { key: 'drifted', label: 'Drifted', className: 'cov-seg--serious' },
] as const

export default function ReportsPage() {
  const [windowDays, setWindowDays] = useState<number>(90)
  const [report, setReport] = useState<CoverageReport | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getCoverageReport(windowDays)
      .then((r) => !cancelled && setReport(r))
      .catch(() => !cancelled && setReport(null))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [windowDays])

  const d = report?.decisions
  const total = d ? Math.max(1, d.reconstructed) : 1

  return (
    <div className="mx-auto max-w-3xl space-y-6 animate-fade-in-up">
      <header className="flex items-end justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold text-foreground">
            Decision Coverage Audit
          </h1>
          <p className="text-sm text-muted-foreground">
            What your engineering organization has decided, and whether execution
            still matches — over the last {windowDays} days.
          </p>
        </div>
        <div className="flex gap-1">
          {WINDOWS.map((w) => (
            <button
              key={w}
              type="button"
              onClick={() => setWindowDays(w)}
              className={`cov-window-btn ${w === windowDays ? 'cov-window-btn--active' : ''}`}
            >
              {w}d
            </button>
          ))}
        </div>
      </header>

      {loading || !d ? (
        <Skeleton className="h-64 w-full rounded-xl" />
      ) : (
        <>
          {/* Hero number */}
          <div className="dashboard-panel p-6">
            <p className="cov-hero-num tabular-nums">{d.reconstructed}</p>
            <p className="text-sm text-muted-foreground">
              consequential decisions reconstructed
            </p>

            {/* Alignment breakdown bar */}
            <div className="mt-5 flex h-2.5 overflow-hidden rounded-full">
              {SEGMENTS.map((s) => {
                const value = d[s.key]
                const pct = (value / total) * 100
                return value > 0 ? (
                  <div
                    key={s.key}
                    className={`cov-seg ${s.className}`}
                    style={{ width: `${pct}%` }}
                    title={`${s.label}: ${value}`}
                  />
                ) : null
              })}
            </div>
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5">
              {SEGMENTS.map((s) => (
                <span key={s.key} className="cov-legend">
                  <span className={`cov-dot ${s.className}`} aria-hidden="true" />
                  {s.label}
                  <span className="tabular-nums text-foreground">{d[s.key]}</span>
                </span>
              ))}
            </div>
          </div>

          {/* Drift outcomes */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatTile label="Drifts detected" value={report.drifts.total} />
            <StatTile label="Confirmed" value={report.drifts.confirmed} />
            <StatTile label="Resolved" value={report.drifts.resolved} />
            <StatTile
              label="Caused a change"
              value={report.drifts.actioned}
              emphasis
            />
          </div>

          {Object.keys(report.drifts.resolution_breakdown).length > 0 && (
            <div className="dashboard-panel p-5">
              <h2 className="decision-panel-label">How drifts were resolved</h2>
              <dl className="mt-3 space-y-2">
                {Object.entries(report.drifts.resolution_breakdown).map(
                  ([type, count]) => (
                    <div key={type} className="flex justify-between text-sm">
                      <dt className="text-muted-foreground">
                        {RESOLUTION_LABELS[type] ?? type}
                      </dt>
                      <dd className="tabular-nums text-foreground">{count}</dd>
                    </div>
                  )
                )}
              </dl>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function StatTile({
  label,
  value,
  emphasis,
}: {
  label: string
  value: number
  emphasis?: boolean
}) {
  return (
    <div className="dashboard-panel p-4">
      <p
        className={`tabular-nums text-2xl font-semibold ${
          emphasis ? 'text-[var(--pulse-attention)]' : 'text-foreground'
        }`}
      >
        {value}
      </p>
      <p className="mt-0.5 text-xs text-muted-foreground">{label}</p>
    </div>
  )
}
