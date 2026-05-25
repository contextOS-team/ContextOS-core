'use client'

import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Skeleton } from '@/components/ui/skeleton'
import type {
  MissedDecisionLegalAction,
  MissedDecisionReviewSuggestion,
} from '@/lib/api'

const SUPPORT_COPY = 'Decisions found in recent syncs that need a quick call.'
const ERROR_COPY = 'Could not load missed-decision suggestions. Refresh the dashboard or open Activity to confirm the source sync completed.'
const ACTION_ERROR_COPY = 'Could not update this suggestion. Try again.'

type PendingAction =
  | 'confirm'
  | 'add_evidence'
  | 'defer'
  | 'reject'
  | 'ignore_duplicate'

interface NeedsReviewSuggestionsProps {
  suggestions: MissedDecisionReviewSuggestion[]
  isLoading?: boolean
  error?: string | null
  workspaceId?: string | null
  limit?: number
  onSaveAsNewDecision: (candidateId: string) => Promise<void> | void
  onAddAsEvidence: (candidateId: string) => Promise<void> | void
  onDefer: (candidateId: string) => Promise<void> | void
  onDismiss: (candidateId: string) => Promise<void> | void
  onIgnoreDuplicate: (candidateId: string) => Promise<void> | void
}

function hasAction(
  suggestion: MissedDecisionReviewSuggestion,
  action: MissedDecisionLegalAction
): boolean {
  return suggestion.legal_actions.includes(action)
}

function confidenceLabel(confidence: MissedDecisionReviewSuggestion['confidence']): string {
  return `${confidence.replaceAll('_', ' ')} confidence`
}

function sourceLabel(sourceLink: string): string {
  if (sourceLink.startsWith('/')) return 'Source reference'

  try {
    const host = new URL(sourceLink).hostname.toLowerCase()
    if (host.includes('slack')) return 'Slack source'
    if (host.includes('notion')) return 'Notion source'
    if (host.includes('fathom')) return 'Fathom source'
    if (host.includes('github')) return 'GitHub source'
    if (host.includes('gitlab')) return 'GitLab source'
  } catch {
    return 'Source'
  }

  return 'Source'
}

function visibleSuggestions(
  suggestions: MissedDecisionReviewSuggestion[],
  workspaceId: string | null | undefined,
  limit: number
): MissedDecisionReviewSuggestion[] {
  return suggestions
    .filter((suggestion) => suggestion.status === 'surfaced')
    .filter((suggestion) => !workspaceId || suggestion.workspace_id === workspaceId)
    .filter((suggestion) => suggestion.source_quote.length > 0 && suggestion.source_link.length > 0)
    .slice(0, Math.min(Math.max(limit, 0), 5))
}

function DestructiveActionDialog({
  triggerLabel,
  title,
  description,
  confirmLabel,
  disabled,
  onConfirm,
}: {
  triggerLabel: string
  title: string
  description: string
  confirmLabel: string
  disabled: boolean
  onConfirm: () => Promise<void> | void
}) {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={disabled}
          className="min-h-10 px-3 text-[var(--pulse-muted)] hover:bg-white/[0.045] hover:text-[var(--pulse-foreground)]"
        >
          {triggerLabel}
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent className="border-white/[0.08] bg-[#090a0d] text-[var(--pulse-foreground)] sm:rounded-lg">
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>
            {description}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Keep candidate</AlertDialogCancel>
          <AlertDialogAction
            className="bg-destructive text-white hover:bg-destructive/90"
            onClick={() => {
              void onConfirm()
            }}
          >
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

function MissedDecisionSuggestionRow({
  suggestion,
  onSaveAsNewDecision,
  onAddAsEvidence,
  onDefer,
  onDismiss,
  onIgnoreDuplicate,
}: {
  suggestion: MissedDecisionReviewSuggestion
  onSaveAsNewDecision: (candidateId: string) => Promise<void> | void
  onAddAsEvidence: (candidateId: string) => Promise<void> | void
  onDefer: (candidateId: string) => Promise<void> | void
  onDismiss: (candidateId: string) => Promise<void> | void
  onIgnoreDuplicate: (candidateId: string) => Promise<void> | void
}) {
  const [pending, setPending] = useState<PendingAction | null>(null)
  const [error, setError] = useState<string | null>(null)
  const disabled = pending !== null
  const people = suggestion.people.slice(0, 3).join(', ')
  const systems = suggestion.affected_systems.slice(0, 3)
  const match = suggestion.possible_existing_match
  const possibleExistingTitle = match?.title ?? match?.entity_id ?? null
  const showExistingMatch = Boolean(
    possibleExistingTitle && match?.match_status !== 'no_match'
  )

  async function run(
    action: PendingAction,
    handler: (candidateId: string) => Promise<void> | void
  ) {
    setPending(action)
    setError(null)
    try {
      await handler(suggestion.id)
    } catch {
      setError(ACTION_ERROR_COPY)
    } finally {
      setPending(null)
    }
  }

  return (
    <div className="pulse-row px-4 py-4">
      <div className="space-y-3">
        <div className="space-y-1.5">
          <h3 className="pulse-title text-[16px] font-semibold leading-snug text-[var(--pulse-foreground)]">
            {suggestion.inferred_decision}
          </h3>
          <p className="line-clamp-2 text-sm leading-6 text-[var(--pulse-muted)]">
            {suggestion.inferred_rationale}
          </p>
        </div>

        <blockquote className="pulse-quote mt-0">
          <p className="line-clamp-2 text-sm leading-relaxed text-[var(--pulse-foreground)]">
            &ldquo;{suggestion.source_quote}&rdquo;
          </p>
        </blockquote>

        <div className="pulse-meta">
          <a
            href={suggestion.source_link}
            className="pulse-tag transition-colors hover:text-[var(--pulse-foreground)]"
          >
            {sourceLabel(suggestion.source_link)}
          </a>
          <span>{confidenceLabel(suggestion.confidence)}</span>
          {people && <span>{people}</span>}
        </div>

        {systems.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {systems.map((system) => (
              <span key={system} className="pulse-tag">
                {system}
              </span>
            ))}
          </div>
        )}

        {showExistingMatch && (
          <p className="text-xs leading-5 text-[var(--pulse-muted)]">
            Possible existing decision: {possibleExistingTitle}
          </p>
        )}

        {error && <p className="text-xs text-destructive">{error}</p>}

        <div className="flex flex-wrap items-center gap-2 pt-0.5">
          {hasAction(suggestion, 'add_evidence') && (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={disabled}
              className="min-h-10 bg-white/[0.065] px-3 text-[var(--pulse-foreground)] hover:bg-white/[0.09]"
              onClick={() => void run('add_evidence', onAddAsEvidence)}
            >
              {pending === 'add_evidence' ? 'Adding evidence...' : 'Add as evidence'}
            </Button>
          )}
          {hasAction(suggestion, 'confirm') && (
            <Button
              type="button"
              size="sm"
              disabled={disabled}
              className="min-h-10 px-3"
              onClick={() => void run('confirm', onSaveAsNewDecision)}
            >
              {pending === 'confirm' ? 'Saving...' : 'Save as new decision'}
            </Button>
          )}
          {hasAction(suggestion, 'defer') && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={disabled}
              className="min-h-10 px-3 text-[var(--pulse-muted)] hover:bg-white/[0.045] hover:text-[var(--pulse-foreground)]"
              onClick={() => void run('defer', onDefer)}
            >
              {pending === 'defer' ? 'Deferring...' : 'Defer'}
            </Button>
          )}
          {hasAction(suggestion, 'reject') && (
            <DestructiveActionDialog
              triggerLabel="Dismiss candidate"
              title="Dismiss candidate"
              description="Dismiss this candidate without creating decision memory."
              confirmLabel={pending === 'reject' ? 'Dismissing...' : 'Dismiss candidate'}
              disabled={disabled}
              onConfirm={() => run('reject', onDismiss)}
            />
          )}
          {hasAction(suggestion, 'ignore_duplicate') && (
            <DestructiveActionDialog
              triggerLabel="Ignore duplicate"
              title="Ignore duplicate"
              description="Keep the existing decision and hide this candidate."
              confirmLabel={pending === 'ignore_duplicate' ? 'Ignoring...' : 'Ignore duplicate'}
              disabled={disabled}
              onConfirm={() => run('ignore_duplicate', onIgnoreDuplicate)}
            />
          )}
        </div>
      </div>
    </div>
  )
}

function LoadingRows() {
  return (
    <div className="pulse-list-panel">
      {[0, 1, 2].map((item) => (
        <div key={item} className="space-y-3 px-4 py-4">
          <Skeleton className="h-4 w-4/5" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      ))}
    </div>
  )
}

export function NeedsReviewSuggestions({
  suggestions,
  isLoading = false,
  error = null,
  workspaceId,
  limit = 3,
  onSaveAsNewDecision,
  onAddAsEvidence,
  onDefer,
  onDismiss,
  onIgnoreDuplicate,
}: NeedsReviewSuggestionsProps) {
  const visible = useMemo(
    () => visibleSuggestions(suggestions, workspaceId, limit),
    [suggestions, workspaceId, limit]
  )

  if (!isLoading && !error && visible.length === 0) return null

  return (
    <section className="space-y-3">
      <div className="space-y-1">
        <h2 className="pulse-section-label">Needs review</h2>
        <p className="text-sm leading-6 text-[var(--pulse-muted)]">
          {SUPPORT_COPY}
        </p>
      </div>

      {isLoading ? (
        <LoadingRows />
      ) : error ? (
        <div className="pulse-list-panel">
          <div className="px-4 py-4 text-sm leading-6 text-destructive">
            {error || ERROR_COPY}
          </div>
        </div>
      ) : (
        <div className="pulse-list-panel">
          {visible.map((suggestion) => (
            <MissedDecisionSuggestionRow
              key={suggestion.id}
              suggestion={suggestion}
              onSaveAsNewDecision={onSaveAsNewDecision}
              onAddAsEvidence={onAddAsEvidence}
              onDefer={onDefer}
              onDismiss={onDismiss}
              onIgnoreDuplicate={onIgnoreDuplicate}
            />
          ))}
        </div>
      )}
    </section>
  )
}
