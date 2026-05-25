'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import {
  dismissSuggestion,
  getAllSuggestions,
  reopenSuggestion,
  resolveSuggestion,
  snoozeSuggestion,
  type SuggestionItem,
} from '@/lib/api'
import { suggestionAction } from '@/lib/suggestions'

type RowAction = 'dismiss' | 'snooze' | 'resolve' | 'reopen'

function statusLabel(status: SuggestionItem['status']): string {
  if (status === 'open') return 'open'
  if (status === 'snoozed') return 'snoozed'
  if (status === 'resolved') return 'resolved'
  return 'dismissed'
}

export default function SuggestionsPage() {
  const [items, setItems] = useState<SuggestionItem[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pendingId, setPendingId] = useState<string | null>(null)

  async function load() {
    setIsLoading(true)
    setError(null)
    try {
      setItems(await getAllSuggestions())
    } catch {
      setError('Could not load suggestions. Refresh the dashboard or try again.')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  async function run(item: SuggestionItem, action: RowAction) {
    setPendingId(item.id)
    setError(null)
    try {
      const updated = action === 'dismiss'
        ? await dismissSuggestion(item.id)
        : action === 'snooze'
          ? await snoozeSuggestion(item.id)
          : action === 'resolve'
            ? await resolveSuggestion(item.id)
            : await reopenSuggestion(item.id)

      setItems((current) => current.map((row) => row.id === updated.id ? updated : row))
    } catch {
      setError('Could not update this suggestion. Try again.')
    } finally {
      setPendingId(null)
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6">
      <div className="space-y-2">
        <Link href="/dashboard" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
          Dashboard
        </Link>
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Needs review</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Source-backed suggestions that need a quick decision-memory review.
          </p>
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {isLoading ? (
        <div className="dashboard-panel p-6 text-sm text-muted-foreground">
          Loading suggestions...
        </div>
      ) : items.length === 0 ? (
        <div className="dashboard-panel p-6">
          <h2 className="text-sm font-medium text-foreground">No suggestions need review</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Source-backed suggestions will appear here when ContextOS finds a specific decision evidence gap.
          </p>
        </div>
      ) : (
        <div className="dashboard-list-panel space-y-0.5 overflow-hidden">
          {items.map((item) => {
            const primaryAction = suggestionAction(item)

            return (
              <div key={item.id} className="dashboard-list-row px-4 py-4">
                <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      {primaryAction ? (
                        <Link
                          href={primaryAction.href}
                          className="text-sm font-semibold text-foreground transition-colors hover:text-foreground/80"
                        >
                          {item.title}
                        </Link>
                      ) : (
                        <h2 className="text-sm font-semibold text-foreground">{item.title}</h2>
                      )}
                      <span className="rounded-md border border-border px-2 py-1 text-xs text-muted-foreground">
                        {statusLabel(item.status)}
                      </span>
                      <span className="rounded-md border border-border px-2 py-1 text-xs text-muted-foreground">
                        {item.priority}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.body}</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {primaryAction && item.status !== 'dismissed' && item.status !== 'resolved' && (
                      <Link
                        href={primaryAction.href}
                        className="inline-flex min-h-10 items-center rounded-md px-3 text-sm font-medium text-foreground transition-[background-color,transform] hover:bg-white/[0.055] active:scale-[0.96]"
                      >
                        {primaryAction.label}
                      </Link>
                    )}
                    {item.status === 'dismissed' || item.status === 'resolved' ? (
                      <button
                        type="button"
                        disabled={pendingId === item.id}
                        onClick={() => void run(item, 'reopen')}
                        className="inline-flex min-h-10 items-center rounded-md px-3 text-sm text-foreground transition-[background-color,transform] hover:bg-white/[0.055] active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Reopen
                      </button>
                    ) : (
                      <>
                        <button
                          type="button"
                          disabled={pendingId === item.id}
                          onClick={() => void run(item, 'snooze')}
                          className="inline-flex min-h-10 items-center rounded-md px-3 text-sm text-muted-foreground transition-[color,background-color,transform] hover:bg-white/[0.045] hover:text-foreground active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Snooze
                        </button>
                        <button
                          type="button"
                          disabled={pendingId === item.id}
                          onClick={() => void run(item, 'resolve')}
                          className="inline-flex min-h-10 items-center rounded-md px-3 text-sm text-muted-foreground transition-[color,background-color,transform] hover:bg-white/[0.045] hover:text-foreground active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Mark resolved
                        </button>
                        <button
                          type="button"
                          disabled={pendingId === item.id}
                          onClick={() => void run(item, 'dismiss')}
                          className="inline-flex min-h-10 items-center rounded-md px-3 text-sm text-muted-foreground transition-[color,background-color,transform] hover:bg-white/[0.045] hover:text-foreground active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Dismiss
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
