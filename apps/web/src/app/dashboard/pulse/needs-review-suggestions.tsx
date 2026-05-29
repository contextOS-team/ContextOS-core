'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { Ellipsis, ExternalLink } from 'lucide-react'
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
} from '@/components/ui/alert-dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Skeleton } from '@/components/ui/skeleton'
import type {
  MissedDecisionLegalAction,
  MissedDecisionReviewSuggestion,
} from '@/lib/api'

const SECTION_LABEL = 'Needs review'
const SUPPORT_COPY = 'Missed-decision candidates that need confirmation before becoming decision memory.'
const ERROR_COPY = 'Could not load missed-decision suggestions. Refresh the dashboard or open Activity to confirm the source sync completed.'
const ACTION_ERROR_COPY = 'Could not update this suggestion. Try again.'

type PendingAction =
  | 'confirm'
  | 'add_evidence'
  | 'defer'
  | 'reject'
  | 'ignore_duplicate'
  | ReviewFeedbackReason

type ReviewFeedbackReason =
  | 'not_product_or_engineering_decision'
  | 'low_business_impact'
  | 'wrong_affected_system'

const ACTION_LABELS: Record<MissedDecisionLegalAction, string> = {
  confirm: 'Save as new decision',
  add_evidence: 'Add as evidence',
  defer: 'Defer',
  reject: 'Dismiss candidate',
  ignore_duplicate: 'Ignore duplicate',
}

const ACTION_PENDING_LABELS: Record<MissedDecisionLegalAction, string> = {
  confirm: 'Saving...',
  add_evidence: 'Adding evidence...',
  defer: 'Deferring...',
  reject: 'Dismissing...',
  ignore_duplicate: 'Ignoring...',
}

const FEEDBACK_LABELS: Record<ReviewFeedbackReason, string> = {
  not_product_or_engineering_decision: 'Not a product decision',
  low_business_impact: 'Too low impact',
  wrong_affected_system: 'Wrong affected system',
}

const FEEDBACK_PENDING_LABELS: Record<ReviewFeedbackReason, string> = {
  not_product_or_engineering_decision: 'Marking...',
  low_business_impact: 'Marking low impact...',
  wrong_affected_system: 'Marking wrong system...',
}

const FEEDBACK_REASONS: ReviewFeedbackReason[] = [
  'not_product_or_engineering_decision',
  'low_business_impact',
  'wrong_affected_system',
]

interface NeedsReviewSuggestionsProps {
  suggestions: MissedDecisionReviewSuggestion[]
  isLoading?: boolean
  error?: string | null
  workspaceId?: string | null
  limit?: number
  onSaveAsNewDecision: (candidateId: string) => Promise<void> | void
  onAddAsEvidence: (candidateId: string, targetDecisionId?: string | null) => Promise<void> | void
  onDefer: (candidateId: string) => Promise<void> | void
  onDismiss: (candidateId: string, reason?: string | null) => Promise<void> | void
  onIgnoreDuplicate: (candidateId: string) => Promise<void> | void
}

function confidenceLabel(confidence: MissedDecisionReviewSuggestion['confidence']): string {
  return `${confidence.replaceAll('_', ' ')} confidence`
}

function titleLabel(value: string | null | undefined): string {
  const label = compactLabel(value)
  return label ? `${label[0].toUpperCase()}${label.slice(1)}` : ''
}

function compactLabel(value: string | null | undefined): string {
  return (value ?? '').replaceAll('_', ' ').trim()
}

function hostMatches(host: string, domain: string): boolean {
  return host === domain || host.endsWith(`.${domain}`)
}

function sourceLabel(sourceLink: string): string {
  if (sourceLink.startsWith('/')) return 'Source reference'

  try {
    const host = new URL(sourceLink).hostname.toLowerCase()
    if (hostMatches(host, 'slack.com')) return 'Slack source'
    if (hostMatches(host, 'notion.so') || hostMatches(host, 'notion.site')) {
      return 'Notion source'
    }
    if (
      hostMatches(host, 't.me')
      || hostMatches(host, 'telegram.me')
      || hostMatches(host, 'telegram.org')
    ) {
      return 'Telegram source'
    }
    if (hostMatches(host, 'fathom.video')) return 'Fathom source'
    if (hostMatches(host, 'github.com')) return 'GitHub source'
    if (hostMatches(host, 'gitlab.com')) return 'GitLab source'
  } catch {
    return 'Source'
  }

  return 'Source'
}

function sourceActionLabel(sourceLink: string): string {
  return `Open ${sourceLabel(sourceLink).toLowerCase()}`
}

function isExternalSource(sourceLink: string): boolean {
  return sourceLink.startsWith('http://') || sourceLink.startsWith('https://')
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

function actionLabel(action: MissedDecisionLegalAction): string {
  return ACTION_LABELS[action]
}

function pendingLabel(action: MissedDecisionLegalAction): string {
  return ACTION_PENDING_LABELS[action]
}

function feedbackLabel(reason: ReviewFeedbackReason): string {
  return FEEDBACK_LABELS[reason]
}

function feedbackPendingLabel(reason: ReviewFeedbackReason): string {
  return FEEDBACK_PENDING_LABELS[reason]
}

function isFeedbackReason(action: PendingAction): action is ReviewFeedbackReason {
  return (
    action === 'not_product_or_engineering_decision'
    || action === 'low_business_impact'
    || action === 'wrong_affected_system'
  )
}

function pendingActionLabel(action: PendingAction): string {
  return isFeedbackReason(action)
    ? feedbackLabel(action)
    : actionLabel(action)
}

function pendingActionProgressLabel(action: PendingAction): string {
  return isFeedbackReason(action)
    ? feedbackPendingLabel(action)
    : pendingLabel(action)
}

function reviewReasonRows(suggestion: MissedDecisionReviewSuggestion): Array<{
  label: string
  value: string
  detail?: string
}> {
  const context = suggestion.review_context ?? {}
  const artifactType = titleLabel(context.expected_artifact_type)
  const affectedObject = context.affected_object?.trim()
  const searchedSources = context.searched_sources?.filter(Boolean).join(', ')
  const impactLevel = compactLabel(context.impact_level)

  return [
    artifactType
      ? {
          label: 'Missing artifact',
          value: artifactType,
          detail: context.expected_artifact?.trim() || context.missing_artifact_reason?.trim(),
        }
      : null,
    affectedObject
      ? {
          label: 'Affected object',
          value: affectedObject,
        }
      : null,
    searchedSources
      ? {
          label: 'Searched sources',
          value: searchedSources,
        }
      : null,
    impactLevel
      ? {
          label: 'Impact',
          value: `${impactLevel} impact`,
          detail: context.impact_reason?.trim(),
        }
      : null,
  ].filter((item): item is { label: string; value: string; detail?: string } => Boolean(item))
}

function recommendedLegalAction(
  suggestion: MissedDecisionReviewSuggestion
): MissedDecisionLegalAction | null {
  const legal = availableLegalActions(suggestion)
  const recommended = suggestion.recommended_action
  const preferred = recommended === 'add_as_evidence' && targetDecisionId(suggestion)
    ? 'add_evidence'
    : recommended === 'save_as_new_decision'
      ? 'confirm'
      : recommended === 'ignore_duplicate'
        ? 'ignore_duplicate'
        : null

  if (preferred && legal.includes(preferred)) return preferred
  if (legal.includes('add_evidence')) return 'add_evidence'
  if (legal.includes('confirm')) return 'confirm'
  return legal[0] ?? null
}

function availableLegalActions(
  suggestion: MissedDecisionReviewSuggestion
): MissedDecisionLegalAction[] {
  if (targetDecisionId(suggestion)) return suggestion.legal_actions
  return suggestion.legal_actions.filter((action) => action !== 'add_evidence')
}

function targetDecisionId(
  suggestion: MissedDecisionReviewSuggestion
): string | null {
  const match = suggestion.possible_existing_match
  if (match?.entity_type === 'Decision' && match.entity_id) return match.entity_id
  return null
}

function destructiveCopy(action: PendingAction): {
  title: string
  description: string
} {
  if (action === 'ignore_duplicate') {
    return {
      title: 'Ignore duplicate',
      description: 'Keep the existing decision and hide this candidate.',
    }
  }
  return {
    title: 'Dismiss candidate',
    description: 'Dismiss this candidate without creating decision memory.',
  }
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
  onAddAsEvidence: (candidateId: string, targetDecisionId?: string | null) => Promise<void> | void
  onDefer: (candidateId: string) => Promise<void> | void
  onDismiss: (candidateId: string, reason?: string | null) => Promise<void> | void
  onIgnoreDuplicate: (candidateId: string) => Promise<void> | void
}) {
  const [pending, setPending] = useState<PendingAction | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [expandedQuote, setExpandedQuote] = useState(false)
  const [confirming, setConfirming] = useState<PendingAction | null>(null)
  const disabled = pending !== null
  const people = suggestion.people.slice(0, 3).join(', ')
  const systems = suggestion.affected_systems.slice(0, 3)
  const match = suggestion.possible_existing_match
  const possibleExistingTitle = match?.title?.trim() || null
  const primaryAction = recommendedLegalAction(suggestion)
  const secondaryActions = availableLegalActions(suggestion)
    .filter((action) => action !== primaryAction)
  const selectedTargetDecisionId = targetDecisionId(suggestion)
  const canExpandQuote = suggestion.source_quote.length > 180
  const showExistingMatch = Boolean(
    possibleExistingTitle && match?.match_status !== 'no_match'
  )
  const reasonRows = reviewReasonRows(suggestion)
  const confirmingCopy = confirming ? destructiveCopy(confirming) : null

  async function run(action: PendingAction) {
    setPending(action)
    setError(null)
    try {
      if (action === 'confirm') await onSaveAsNewDecision(suggestion.id)
      if (action === 'add_evidence') {
        await onAddAsEvidence(suggestion.id, selectedTargetDecisionId)
      }
      if (action === 'defer') await onDefer(suggestion.id)
      if (action === 'reject') await onDismiss(suggestion.id)
      if (action === 'ignore_duplicate') await onIgnoreDuplicate(suggestion.id)
      if (isFeedbackReason(action)) await onDismiss(suggestion.id, action)
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
          <p className={`${expandedQuote ? '' : 'line-clamp-3'} text-sm leading-relaxed text-[var(--pulse-foreground)]`}>
            &ldquo;{suggestion.source_quote}&rdquo;
          </p>
          {canExpandQuote && (
            <button
              type="button"
              className="mt-2 text-xs font-medium text-[var(--pulse-attention)] transition-colors hover:text-[var(--pulse-foreground)]"
              onClick={() => setExpandedQuote((value) => !value)}
            >
              {expandedQuote ? 'Collapse quote' : 'Show full quote'}
            </button>
          )}
        </blockquote>

        <div className="pulse-meta">
          <a
            href={suggestion.source_link}
            target={isExternalSource(suggestion.source_link) ? '_blank' : undefined}
            rel={isExternalSource(suggestion.source_link) ? 'noreferrer' : undefined}
            className="pulse-meta-item shrink-0 gap-1.5 rounded-md border border-[var(--pulse-attention)]/40 bg-[var(--pulse-attention)]/10 px-2 py-1 text-xs font-medium text-[var(--pulse-attention)] transition-colors hover:border-[var(--pulse-attention)]/70 hover:bg-[var(--pulse-attention)]/16 hover:text-[var(--pulse-attention)]"
            aria-label={sourceActionLabel(suggestion.source_link)}
          >
            <ExternalLink className="size-3" aria-hidden="true" />
            {sourceActionLabel(suggestion.source_link)}
          </a>
          <span className="pulse-meta-item">{confidenceLabel(suggestion.confidence)}</span>
          {people && <span className="pulse-meta-item">{people}</span>}
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

        {reasonRows.length > 0 && (
          <div className="grid gap-2 rounded-md border border-white/[0.07] bg-white/[0.025] px-3 py-2 sm:grid-cols-2">
            {reasonRows.map((row) => (
              <div key={row.label} className="min-w-0">
                <p className="text-[11px] font-medium uppercase text-[var(--pulse-muted)]">
                  {row.label}
                </p>
                <p className="mt-0.5 truncate text-sm font-medium text-[var(--pulse-foreground)]">
                  {row.value}
                </p>
                {row.detail && (
                  <p className="mt-0.5 line-clamp-2 text-xs leading-5 text-[var(--pulse-muted)]">
                    {row.detail}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}

        {showExistingMatch && (
          <div className="space-y-1 rounded-md border border-white/[0.07] bg-white/[0.025] px-3 py-2">
            <p className="text-xs font-medium uppercase text-[var(--pulse-muted)]">
              Possible existing decision
            </p>
            {match?.href ? (
              <a
                href={match.href}
                className="inline-flex items-center gap-1.5 text-sm font-medium text-[var(--pulse-foreground)] transition-colors hover:text-[var(--pulse-attention)]"
              >
                {possibleExistingTitle}
                <ExternalLink className="size-3" aria-hidden="true" />
              </a>
            ) : (
              <p className="text-sm font-medium text-[var(--pulse-foreground)]">
                {possibleExistingTitle}
              </p>
            )}
            {match?.match_reason && (
              <p className="text-xs leading-5 text-[var(--pulse-muted)]">
                {match.match_reason}
              </p>
            )}
          </div>
        )}

        {primaryAction && (
          <div className="rounded-md border border-[var(--pulse-attention)]/25 bg-[var(--pulse-attention)]/8 px-3 py-2">
            <p className="text-xs font-medium uppercase text-[var(--pulse-muted)]">
              Recommended action
            </p>
            <p className="mt-1 text-sm leading-5 text-[var(--pulse-foreground)]">
              Review this candidate before changing decision memory.
            </p>
          </div>
        )}

        {error && <p className="text-xs text-destructive">{error}</p>}

        <div className="flex items-center gap-2 pt-0.5">
          {primaryAction && (
            <Button
              type="button"
              size="sm"
              disabled={disabled}
              className="min-h-10 px-3"
              onClick={() => {
                if (primaryAction === 'reject' || primaryAction === 'ignore_duplicate') {
                  setConfirming(primaryAction)
                  return
                }
                void run(primaryAction)
              }}
            >
              {pending === primaryAction ? pendingLabel(primaryAction) : actionLabel(primaryAction)}
            </Button>
          )}
          {secondaryActions.length > 0 && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  disabled={disabled}
                  aria-label="Candidate actions"
                  className="inline-flex size-10 items-center justify-center rounded-md text-[var(--pulse-muted)] transition-[background-color,color,transform] hover:bg-white/[0.055] hover:text-[var(--pulse-foreground)] active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Ellipsis className="size-4" aria-hidden="true" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48">
                {secondaryActions.map((action) => (
                  <DropdownMenuItem
                    key={action}
                    variant={action === 'reject' || action === 'ignore_duplicate' ? 'destructive' : undefined}
                    onSelect={() => {
                      if (action === 'reject' || action === 'ignore_duplicate') {
                        setConfirming(action)
                        return
                      }
                      void run(action)
                    }}
                  >
                    {pending === action ? pendingLabel(action) : actionLabel(action)}
                  </DropdownMenuItem>
                ))}
                {FEEDBACK_REASONS.map((reason) => (
                  <DropdownMenuItem
                    key={reason}
                    variant="destructive"
                    onSelect={() => void run(reason)}
                  >
                    {pending === reason ? feedbackPendingLabel(reason) : feedbackLabel(reason)}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </div>
      <AlertDialog
        open={confirming !== null}
        onOpenChange={(open) => {
          if (!open) setConfirming(null)
        }}
      >
        <AlertDialogContent className="border-white/[0.08] bg-[#090a0d] text-[var(--pulse-foreground)] sm:rounded-lg">
          <AlertDialogHeader>
            <AlertDialogTitle>
              {confirmingCopy?.title ?? 'Confirm action'}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {confirmingCopy?.description ?? ''}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep candidate</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-white hover:bg-destructive/90"
              onClick={() => {
                if (confirming) void run(confirming)
              }}
            >
              {confirming && pending === confirming
                ? pendingActionProgressLabel(confirming)
                : confirming
                  ? pendingActionLabel(confirming)
                  : 'Confirm'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
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
        <div className="flex items-center justify-between gap-3">
          <h2 className="pulse-section-label">{SECTION_LABEL}</h2>
          <Link href="/dashboard/suggestions" className="pulse-section-link">
            View all
          </Link>
        </div>
        <p className="text-sm leading-6 text-[var(--pulse-muted)]">{SUPPORT_COPY}</p>
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
