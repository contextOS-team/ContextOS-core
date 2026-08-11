'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { submitDecisionFeedback, type DecisionFeedbackVerdict } from '@/lib/api'

const REVIEW_OPTIONS: Array<{ verdict: DecisionFeedbackVerdict; label: string }> = [
  { verdict: 'correct', label: 'Correct' },
  { verdict: 'wrong', label: 'Wrong' },
  { verdict: 'superseded', label: 'Superseded' },
  { verdict: 'duplicate', label: 'Duplicate' },
  { verdict: 'not_important', label: 'Not important' },
  { verdict: 'missing_evidence', label: 'Missing evidence' },
]

export function DecisionReviewPanel({ decisionId }: { decisionId: string }) {
  const [pending, setPending] = useState<DecisionFeedbackVerdict | null>(null)
  const [submitted, setSubmitted] = useState<DecisionFeedbackVerdict | null>(null)

  async function handleFeedback(verdict: DecisionFeedbackVerdict) {
    setPending(verdict)
    try {
      await submitDecisionFeedback(decisionId, verdict)
      setSubmitted(verdict)
      toast.success('Feedback recorded — it trains the decision filter.')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to record feedback')
    } finally {
      setPending(null)
    }
  }

  return (
    <section className="dashboard-panel p-4">
      <h2 className="decision-panel-label">Review</h2>
      <p className="mt-2 text-xs text-muted-foreground">
        Is this decision record right? Every answer improves extraction.
      </p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {REVIEW_OPTIONS.map(({ verdict, label }) => (
          <button
            key={verdict}
            type="button"
            disabled={pending !== null}
            onClick={() => void handleFeedback(verdict)}
            className={`rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors disabled:opacity-50 ${
              submitted === verdict
                ? 'border-[var(--pulse-attention)]/70 bg-[var(--pulse-attention)]/16 text-[var(--pulse-attention)]'
                : 'border-white/[0.09] text-muted-foreground hover:border-white/[0.2] hover:text-foreground'
            }`}
          >
            {pending === verdict ? '…' : label}
          </button>
        ))}
      </div>
    </section>
  )
}
