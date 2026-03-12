'use client'

import { Check, Circle, Loader2, AlertCircle, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { GenerationStep } from '@/lib/api'
import { SOURCE_LABELS } from '@/lib/api'

// ---------------------------------------------------------------------------
// Friendly error message mapping
// ---------------------------------------------------------------------------

const ERROR_MESSAGES: Record<string, string> = {
  'rate limit': 'Too many requests. Please wait a moment and try again.',
  'timeout': 'The request took too long. Please try again.',
  'unauthorized': 'Your session has expired. Please sign in again.',
  'not found': 'The requested ticket could not be found.',
  'already running': 'A generation is already in progress. Please wait for it to finish.',
  'concurrent': 'A generation is already in progress. Please wait for it to finish.',
  'openai': 'The AI service is temporarily unavailable. Please try again shortly.',
  'anthropic': 'The AI service is temporarily unavailable. Please try again shortly.',
  'connection': 'Could not connect to the server. Check your internet connection.',
  'network': 'Could not connect to the server. Check your internet connection.',
  'internal server error': 'Something went wrong on our end. Please try again.',
  'token': 'Your integration token has expired. Reconnect the integration in Settings.',
}

function friendlyError(raw: string): string {
  const lower = raw.toLowerCase()
  for (const [key, message] of Object.entries(ERROR_MESSAGES)) {
    if (lower.includes(key)) return message
  }
  return 'Something went wrong during generation. Please try again.'
}

interface GenerationProgressProps {
  ticketIdentifier: string
  steps: GenerationStep[]
  status: 'streaming' | 'complete' | 'error' | 'collapsing'
  errorMessage?: string
  onRetry?: () => void
  onDismiss?: () => void
}

function StepIcon({ status, hasResults, syncing }: { status: GenerationStep['status']; hasResults: boolean; syncing?: boolean }) {
  switch (status) {
    case 'waiting':
      return <Circle className="h-4 w-4 text-muted-foreground/40" />
    case 'active':
      return <Loader2 className="h-4 w-4 text-primary animate-spin" />
    case 'complete':
      if (syncing)
        return <Loader2 className="h-4 w-4 text-amber-400 animate-spin" />
      return hasResults
        ? <Check className="h-4 w-4 text-emerald-400" />
        : <Check className="h-4 w-4 text-muted-foreground/50" />
    case 'error':
      return <AlertCircle className="h-4 w-4 text-destructive" />
  }
}

function StepDetail({ step }: { step: GenerationStep }) {
  const isSynthesize = step.source === 'synthesize'
  switch (step.status) {
    case 'waiting':
      return <span>Waiting</span>
    case 'active':
      return <span>{isSynthesize ? 'Generating...' : 'Searching...'}</span>
    case 'complete':
      return <span>{step.detail ?? `${step.count ?? 0} results`}</span>
    case 'error':
      return <span className="text-destructive">{step.detail ?? 'Failed'}</span>
  }
}

export function GenerationProgress({
  ticketIdentifier,
  steps,
  status,
  errorMessage,
  onRetry,
  onDismiss,
}: GenerationProgressProps) {
  const sourceSteps = steps.filter((s) => s.source !== 'synthesize')
  const synthesizeStep = steps.find((s) => s.source === 'synthesize')
  const allSourcesEmpty = sourceSteps.length > 0 &&
    sourceSteps.every((s) => s.status === 'complete' && (s.count ?? 0) === 0 && !s.syncing)

  return (
    <div
      className="rounded-lg border border-border bg-card px-4 py-3 overflow-hidden"
      style={
        status === 'collapsing'
          ? { animation: 'progress-collapse 500ms ease-in forwards' }
          : status === 'complete'
            ? { borderColor: 'oklch(0.75 0.18 170 / 0.2)' }
            : undefined
      }
    >
      {/* Header */}
      <p className="section-label mb-2">
        Generating context for {ticketIdentifier}
      </p>

      {/* Loading state before steps arrive */}
      {steps.length === 0 && status === 'streaming' && (
        <div className="flex items-center gap-3 py-2">
          <Loader2 className="h-4 w-4 text-primary animate-spin" />
          <span className="text-sm text-muted-foreground">Connecting...</span>
        </div>
      )}

      {/* Source steps */}
      <div className="space-y-0.5">
        {sourceSteps.map((step, index) => {
          const hasResults = step.status === 'complete' && (step.count ?? 0) > 0
          const isSyncing = step.status === 'complete' && step.syncing
          const isEmpty = step.status === 'complete' && (step.count ?? 0) === 0 && !isSyncing
          return (
            <div
              key={step.source}
              className={`flex items-center gap-3 py-1 ${
                step.status === 'active'
                  ? 'text-primary'
                  : step.status === 'error'
                    ? 'text-destructive'
                    : isEmpty
                      ? 'opacity-50'
                      : ''
              }`}
              style={{
                animationName: step.status === 'active'
                  ? 'step-slide-in, step-pulse'
                  : 'step-slide-in',
                animationDuration: step.status === 'active'
                  ? '300ms, 1.5s'
                  : '300ms',
                animationTimingFunction: step.status === 'active'
                  ? 'ease-out, ease-in-out'
                  : 'ease-out',
                animationFillMode: step.status === 'active'
                  ? 'both, none'
                  : 'both',
                animationIterationCount: step.status === 'active'
                  ? '1, infinite'
                  : '1',
                animationDelay: `${index * 100}ms`,
              }}
            >
              <StepIcon status={step.status} hasResults={hasResults} syncing={step.syncing} />
              <span className="text-sm font-medium">
                {SOURCE_LABELS[step.source] ?? step.source}
              </span>
              <span className="ml-auto text-xs text-muted-foreground">
                <StepDetail step={step} />
              </span>
            </div>
          )
        })}
      </div>

      {/* Synthesize step — visually separated */}
      {synthesizeStep && (
        <>
          <div className="border-t border-border/50 my-1.5" />
          <div
            className={`flex items-center gap-3 py-1 ${
              synthesizeStep.status === 'active'
                ? 'text-primary'
                : synthesizeStep.status === 'complete'
                  ? 'text-emerald-400'
                  : synthesizeStep.status === 'error'
                    ? 'text-destructive'
                    : ''
            }`}
            style={{
              animationName: synthesizeStep.status === 'active'
                ? 'step-slide-in, step-pulse'
                : 'step-slide-in',
              animationDuration: synthesizeStep.status === 'active'
                ? '300ms, 1.5s'
                : '300ms',
              animationTimingFunction: synthesizeStep.status === 'active'
                ? 'ease-out, ease-in-out'
                : 'ease-out',
              animationFillMode: synthesizeStep.status === 'active'
                ? 'both, none'
                : 'both',
              animationIterationCount: synthesizeStep.status === 'active'
                ? '1, infinite'
                : '1',
              animationDelay: `${sourceSteps.length * 100}ms`,
            }}
          >
            {synthesizeStep.status === 'complete' ? (
              <Sparkles className="h-4 w-4 text-emerald-400" />
            ) : synthesizeStep.status === 'active' ? (
              <Loader2 className="h-4 w-4 text-primary animate-spin" />
            ) : synthesizeStep.status === 'error' ? (
              <AlertCircle className="h-4 w-4 text-destructive" />
            ) : (
              <Circle className="h-4 w-4 text-muted-foreground/40" />
            )}
            <span className="text-sm font-medium">
              {SOURCE_LABELS[synthesizeStep.source] ?? synthesizeStep.source}
            </span>
            <span className="ml-auto text-xs text-muted-foreground">
              <StepDetail step={synthesizeStep} />
            </span>
          </div>
        </>
      )}

      {/* Zero-result summary — elevated when all sources empty */}
      {allSourcesEmpty && sourceSteps.some((s) => s.status === 'complete') && (
        <p className="text-sm text-muted-foreground mt-2 pl-7">
          Context generated from ticket description only
        </p>
      )}

      {/* Error actions */}
      {status === 'error' && (
        <div className="mt-3 flex items-center gap-2">
          {errorMessage && (
            <p className="text-xs text-destructive flex-1">{friendlyError(errorMessage)}</p>
          )}
          {onRetry && (
            <Button variant="ghost" size="sm" onClick={onRetry}>
              Retry
            </Button>
          )}
          {onDismiss && (
            <Button variant="ghost" size="sm" onClick={onDismiss}>
              Dismiss
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
