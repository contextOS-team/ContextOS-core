'use client'

import { Check, Circle, Loader2, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { GenerationStep } from '@/lib/api'
import { SOURCE_LABELS } from '@/lib/api'

interface GenerationProgressProps {
  ticketIdentifier: string
  steps: GenerationStep[]
  status: 'streaming' | 'complete' | 'error' | 'collapsing'
  errorMessage?: string
  onRetry?: () => void
  onDismiss?: () => void
}

function StepIcon({ status }: { status: GenerationStep['status'] }) {
  switch (status) {
    case 'waiting':
      return <Circle className="h-4 w-4 text-muted-foreground" />
    case 'active':
      return <Loader2 className="h-4 w-4 text-primary animate-spin" />
    case 'complete':
      return <Check className="h-4 w-4 text-foreground" />
    case 'error':
      return <AlertCircle className="h-4 w-4 text-destructive" />
  }
}

function StepDetail({ step }: { step: GenerationStep }) {
  switch (step.status) {
    case 'waiting':
      return <span>Waiting</span>
    case 'active':
      return <span>Searching...</span>
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
  return (
    <div
      className="rounded-lg border border-border bg-card p-4 overflow-hidden"
      style={
        status === 'collapsing'
          ? { animation: 'progress-collapse 500ms ease-in forwards' }
          : undefined
      }
    >
      {/* Header */}
      <p className="section-label mb-3">
        Generating context for {ticketIdentifier}
      </p>

      {/* Step list */}
      <div className="space-y-2">
        {steps.map((step, index) => (
          <div
            key={step.source}
            className={`flex items-center gap-3 py-1 ${
              step.status === 'active'
                ? 'text-primary'
                : step.status === 'error'
                  ? 'text-destructive'
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
            <StepIcon status={step.status} />
            <span className="text-sm font-medium">
              {SOURCE_LABELS[step.source] ?? step.source}
            </span>
            <span className="ml-auto text-xs text-muted-foreground">
              <StepDetail step={step} />
            </span>
          </div>
        ))}
      </div>

      {/* Error actions */}
      {status === 'error' && (
        <div className="mt-3 flex items-center gap-2">
          {errorMessage && (
            <p className="text-xs text-destructive flex-1">{errorMessage}</p>
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
