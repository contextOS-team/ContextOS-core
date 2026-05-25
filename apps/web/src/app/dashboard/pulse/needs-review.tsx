'use client'

import Link from 'next/link'
import { useState } from 'react'
import { Ellipsis } from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  dismissSuggestion,
  resolveSuggestion,
  snoozeSuggestion,
  type SuggestionItem,
} from '@/lib/api'
import { suggestionAction } from '@/lib/suggestions'

interface NeedsReviewProps {
  items: SuggestionItem[]
}

type PendingAction = 'dismiss' | 'snooze' | 'resolve'

function titleCaseEvidence(label: string): string {
  if (label === 'design_review') return 'design review'
  return label.replaceAll('_', ' ')
}

function evidenceLabels(suggestion: SuggestionItem): string[] {
  const labels: string[] = []
  const present = suggestion.evidence.present_evidence
  const missing = suggestion.evidence.missing_evidence

  if (Array.isArray(present)) {
    labels.push(
      ...present
        .filter((item): item is string => typeof item === 'string' && item.length > 0)
        .map((label) => `Has ${label}`)
    )
  }

  if (Array.isArray(missing)) {
    labels.push(
      ...missing
        .filter((item): item is string => typeof item === 'string' && item.length > 0)
        .map((label) => `Missing ${titleCaseEvidence(label)}`)
    )
  }

  if (labels.length === 0 && suggestion.entity_type) labels.push(suggestion.entity_type)
  return labels.slice(0, 2)
}

function suggestionReason(suggestion: SuggestionItem): string {
  const assessment = suggestion.details.coverage_assessment
  if (
    assessment &&
    typeof assessment === 'object' &&
    'reason' in assessment &&
    typeof assessment.reason === 'string' &&
    assessment.reason.length > 0
  ) {
    return assessment.reason
  }

  const snippets = suggestion.evidence.snippets
  if (Array.isArray(snippets)) {
    const snippet = snippets.find(
      (item): item is string => typeof item === 'string' && item.length > 0
    )
    if (snippet) return snippet
  }

  return suggestion.body
}

function SuggestionRow({
  suggestion,
  onHide,
}: {
  suggestion: SuggestionItem
  onHide: (id: string) => void
}) {
  const [pending, setPending] = useState<PendingAction | null>(null)
  const [error, setError] = useState<string | null>(null)
  const labels = evidenceLabels(suggestion)
  const primaryAction = suggestionAction(suggestion)
  const reason = suggestionReason(suggestion)

  async function run(action: PendingAction) {
    setPending(action)
    setError(null)
    try {
      if (action === 'dismiss') await dismissSuggestion(suggestion.id)
      if (action === 'snooze') await snoozeSuggestion(suggestion.id)
      if (action === 'resolve') await resolveSuggestion(suggestion.id)
      onHide(suggestion.id)
    } catch {
      setError('Could not update this suggestion. Try again.')
    } finally {
      setPending(null)
    }
  }

  return (
    <div className="pulse-row px-4 py-3.5">
      <div className="space-y-3">
        <div className="space-y-1">
          {primaryAction ? (
            <Link
              href={primaryAction.href}
              className="line-clamp-2 text-sm font-semibold leading-snug text-[var(--pulse-foreground)] transition-colors hover:text-foreground/80"
            >
              {suggestion.title}
            </Link>
          ) : (
            <h3 className="line-clamp-2 text-sm font-semibold leading-snug text-[var(--pulse-foreground)]">
              {suggestion.title}
            </h3>
          )}
          <p className="line-clamp-2 text-xs leading-relaxed text-[var(--pulse-muted)]">
            {reason}
          </p>
        </div>

        {labels.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {labels.map((label) => (
              <span key={label} className="pulse-tag">
                {label}
              </span>
            ))}
          </div>
        )}

        {error && <p className="text-xs text-destructive">{error}</p>}

        <div className="flex items-center justify-between gap-3 pt-0.5">
          {primaryAction && (
            <Link
              href={primaryAction.href}
              className="inline-flex min-h-8 items-center rounded-md bg-white/[0.055] px-2.5 text-sm font-medium text-[var(--pulse-foreground)] transition-[background-color,transform] hover:bg-white/[0.08] active:scale-[0.96]"
            >
              {primaryAction.label}
            </Link>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                disabled={pending !== null}
                aria-label="Suggestion actions"
                className="ml-auto inline-flex size-8 items-center justify-center rounded-md text-[var(--pulse-muted)] transition-[background-color,color,transform] hover:bg-white/[0.055] hover:text-[var(--pulse-foreground)] active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Ellipsis className="size-4" aria-hidden="true" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-40">
              <DropdownMenuItem onSelect={() => void run('snooze')}>
                {pending === 'snooze' ? 'Snoozing...' : 'Snooze'}
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => void run('resolve')}>
                {pending === 'resolve' ? 'Resolving...' : 'Mark resolved'}
              </DropdownMenuItem>
              <DropdownMenuItem
                variant="destructive"
                onSelect={() => void run('dismiss')}
              >
                {pending === 'dismiss' ? 'Dismissing...' : 'Dismiss'}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </div>
  )
}

export function NeedsReview({ items }: NeedsReviewProps) {
  const [hiddenIds, setHiddenIds] = useState<Set<string>>(() => new Set())
  const visible = items.filter((item) => !hiddenIds.has(item.id)).slice(0, 2)

  if (visible.length === 0) return null

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="pulse-section-label">Needs review</h2>
        <Link href="/dashboard/suggestions" className="pulse-section-link">
          View all
        </Link>
      </div>
      <div className="pulse-list-panel">
        {visible.map((item) => (
          <SuggestionRow
            key={item.id}
            suggestion={item}
            onHide={(id) => {
              setHiddenIds((current) => new Set(current).add(id))
            }}
          />
        ))}
      </div>
    </section>
  )
}
