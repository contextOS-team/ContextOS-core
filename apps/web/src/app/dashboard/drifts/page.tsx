'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { toast } from 'sonner'
import { Skeleton } from '@/components/ui/skeleton'
import {
  confirmDrift,
  dismissDrift,
  listDrifts,
  resolveDrift,
  type DriftItem,
  type DriftResolutionType,
} from '@/lib/api'

const RESOLUTIONS: Array<{ value: DriftResolutionType; label: string }> = [
  { value: 'jira_updated', label: 'Jira updated' },
  { value: 'linear_updated', label: 'Linear updated' },
  { value: 'doc_updated', label: 'Doc updated' },
  { value: 'implementation_changed', label: 'Implementation changed' },
  { value: 'work_cancelled', label: 'Work cancelled' },
  { value: 'timeline_changed', label: 'Timeline changed' },
  { value: 'intentional_exception', label: 'Intentional exception' },
  { value: 'other', label: 'Other' },
]

const SEVERITY_CLASS: Record<string, string> = {
  high: 'drift-sev drift-sev--high',
  medium: 'drift-sev drift-sev--medium',
  low: 'drift-sev drift-sev--low',
}

export default function DriftsPage() {
  const [drifts, setDrifts] = useState<DriftItem[] | null>(null)
  const [pending, setPending] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    listDrifts('open')
      .then((r) => {
        if (!cancelled) setDrifts(r.drifts)
      })
      .catch(() => {
        if (!cancelled) setDrifts([])
      })
    return () => {
      cancelled = true
    }
  }, [])

  function remove(id: string) {
    setDrifts((cur) => (cur ? cur.filter((d) => d.id !== id) : cur))
  }

  async function act(id: string, fn: () => Promise<unknown>, msg: string) {
    setPending(id)
    try {
      await fn()
      remove(id)
      toast.success(msg)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Action failed')
    } finally {
      setPending(null)
    }
  }

  if (drifts === null) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32 w-full rounded-xl" />
        <Skeleton className="h-32 w-full rounded-xl" />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-5 animate-fade-in-up">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold text-foreground">Decision Drift</h1>
        <p className="text-sm text-muted-foreground">
          Where execution no longer matches a decision the team has made. Each
          finding survived a skeptical verification pass.
        </p>
      </header>

      {drifts.length === 0 ? (
        <div className="dashboard-panel p-8 text-center">
          <p className="text-sm text-muted-foreground">
            No open drift. Execution currently matches your active decisions.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {drifts.map((d) => (
            <article key={d.id} className="dashboard-panel p-5 space-y-3">
              <div className="flex items-start justify-between gap-3">
                <p className="text-base font-medium leading-snug text-foreground">
                  {d.summary}
                </p>
                <span className={SEVERITY_CLASS[d.severity] ?? 'drift-sev'}>
                  {d.severity}
                </span>
              </div>

              {d.decision_statement && (
                <Link
                  href={`/dashboard/decisions/${encodeURIComponent(d.decision_id)}`}
                  className="block text-xs text-muted-foreground hover:text-foreground"
                >
                  Decision: &ldquo;{d.decision_statement}&rdquo;
                </Link>
              )}

              <div className="flex flex-wrap items-center gap-2 pt-1">
                <button
                  type="button"
                  disabled={pending === d.id}
                  onClick={() =>
                    void act(d.id, () => confirmDrift(d.id), 'Confirmed as real drift')
                  }
                  className="drift-btn drift-btn--primary"
                >
                  Confirm
                </button>
                <button
                  type="button"
                  disabled={pending === d.id}
                  onClick={() =>
                    void act(
                      d.id,
                      () => dismissDrift(d.id),
                      'Marked false positive — trains the verifier'
                    )
                  }
                  className="drift-btn"
                >
                  False positive
                </button>
                <select
                  disabled={pending === d.id}
                  defaultValue=""
                  onChange={(e) => {
                    const v = e.target.value as DriftResolutionType
                    if (v) {
                      void act(
                        d.id,
                        () => resolveDrift(d.id, v),
                        'Resolved — counted as a drift that caused a change'
                      )
                    }
                  }}
                  className="drift-btn drift-resolve-select"
                  aria-label="Mark resolved with a resolution type"
                >
                  <option value="" disabled>
                    Resolve as…
                  </option>
                  {RESOLUTIONS.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
