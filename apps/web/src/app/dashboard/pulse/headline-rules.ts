import { formatLongRelativeTime } from '@/lib/utils'
import type { Delta, HeadlineCopy } from './types'

function pluralize(count: number, singular: string, plural = `${singular}s`): string {
  return count === 1 ? singular : plural
}

/**
 * Pure headline copy rules for the Phase 41 dashboard pulse surface.
 *
 * Branch C intentionally runs before the needs-you branch: a stale assigned
 * item cannot override the "Quiet day." headline when there are no new events.
 */
export function computeHeadline(
  delta: Delta,
  lastVisitedAt: Date | null,
  now: Date = new Date()
): HeadlineCopy {
  void now

  const since = lastVisitedAt ? formatLongRelativeTime(lastVisitedAt.toISOString()) : 'first visit'

  if (delta.decisions.count === 0 && delta.sources.count === 0) {
    return {
      headline: 'Quiet day.',
      subtext: `Nothing new since you last looked, ${since}.`,
    }
  }

  if (delta.needsYou.topUrgentItem) {
    const { person, ticketId, sinceDay } = delta.needsYou.topUrgentItem
    const decisionRemainder = Math.max(0, delta.decisions.count - 1)
    const sourceText = `${delta.sources.count} new ${pluralize(delta.sources.count, 'source')}`

    return {
      headline: `${person} is waiting on ${ticketId} since ${sinceDay}.`,
      subtext:
        decisionRemainder > 0
          ? `${decisionRemainder} more ${pluralize(decisionRemainder, 'decision')} and ${sourceText} since you last looked, ${since}.`
          : `${sourceText} since you last looked, ${since}.`,
    }
  }

  return {
    headline: `${delta.decisions.count} ${pluralize(delta.decisions.count, 'decision')} and ${delta.sources.count} ${pluralize(delta.sources.count, 'source')} of new context since you last looked.`,
    subtext: `Since you last looked, ${since}.`,
  }
}
