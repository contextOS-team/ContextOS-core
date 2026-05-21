import { formatLongRelativeTime } from '@/lib/utils'
import type { Delta, HeadlineCopy } from './types'

function pluralize(count: number, singular: string, plural = `${singular}s`): string {
  return count === 1 ? singular : plural
}

function joinParts(parts: string[]): string {
  if (parts.length <= 1) return parts[0] ?? ''
  return `${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}`
}

function bucketSummary(decisions: number, sources: number): string {
  const parts: string[] = []
  if (decisions > 0) parts.push(`${decisions} ${pluralize(decisions, 'decision')}`)
  if (sources > 0) parts.push(`${sources} source ${pluralize(sources, 'update')}`)
  return joinParts(parts)
}

/**
 * Pure headline copy rules for the Phase 41 dashboard pulse surface.
 *
 * Branch C intentionally runs before the needs-you branch: a stale assigned
 * item cannot override the all-caught-up headline when there are no new events.
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
      headline: 'No new activity since your last visit.',
      subtext: `Nothing new since your last visit, ${since}.`,
    }
  }

  if (delta.needsYou.topUrgentItem) {
    const { person, ticketId, sinceDay } = delta.needsYou.topUrgentItem
    const decisionRemainder = Math.max(0, delta.decisions.count - 1)
    const remainingSummary = bucketSummary(decisionRemainder, delta.sources.count)

    return {
      headline: `${person} has been waiting on ${ticketId} since ${sinceDay}.`,
      subtext: remainingSummary
        ? `${remainingSummary} since your last visit, ${since}.`
        : `New activity since your last visit, ${since}.`,
    }
  }

  const summary = bucketSummary(delta.decisions.count, delta.sources.count)

  return {
    headline: `${summary} since your last visit.`,
    subtext: `Since your last visit, ${since}.`,
  }
}
