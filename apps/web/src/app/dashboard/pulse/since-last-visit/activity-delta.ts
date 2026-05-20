import { createClient } from '@/lib/supabase/client'
import type { Delta, NeedsYouItem } from '../types'

export const DECISION_EVENT_TYPES = ['context_generated', 'messages_digest'] as const
export const SOURCE_EVENT_TYPES = [
  'ticket_created',
  'pr_merged',
  'meeting_recorded',
  'page_created',
] as const

export interface ActivityDeltaRow {
  id: string
  event_type: string
  created_at: string
}

/**
 * Buckets the Phase 41 since-last-visit activity delta.
 *
 * The event type lists mirror migrations 00031_activity_event_types.sql and
 * 00033_messages_digest_event_type.sql. Needs-you items remain separate so the
 * headline rules can enforce the locked single-item-dominant rule before
 * bucket copy.
 */
export function bucketDelta(
  rows: ReadonlyArray<ActivityDeltaRow>,
  needsYouItems: ReadonlyArray<NeedsYouItem>,
  currentUserId: string
): Delta {
  const decisions = rows
    .filter((row) => DECISION_EVENT_TYPES.includes(row.event_type as (typeof DECISION_EVENT_TYPES)[number]))
    .map((row) => ({ id: row.id, createdAt: row.created_at }))

  const sources = rows
    .filter((row) => SOURCE_EVENT_TYPES.includes(row.event_type as (typeof SOURCE_EVENT_TYPES)[number]))
    .map((row) => ({ id: row.id, createdAt: row.created_at }))

  const assignedNeedsYouItems = needsYouItems
    .filter((item) => item.assignedToCurrentUser)
    .sort((a, b) => b.ageMs - a.ageMs)

  const oldestAssigned = assignedNeedsYouItems[0]

  return {
    decisions: {
      count: decisions.length,
      items: decisions,
    },
    sources: {
      count: sources.length,
      items: sources,
    },
    needsYou: {
      topUrgentItem: oldestAssigned
        ? {
            person: oldestAssigned.person,
            ticketId: oldestAssigned.ticketId,
            sinceDay: oldestAssigned.sinceDay,
          }
        : null,
      items: needsYouItems,
    },
  }
}

export async function fetchActivityDelta(
  workspaceId: string,
  since: Date | null
): Promise<ActivityDeltaRow[]> {
  const supabase = createClient()
  let query = supabase
    .from('activity_events')
    .select('*')
    .eq('workspace_id', workspaceId)
    .order('created_at', { ascending: false })
    .limit(200)

  if (since) {
    query = query.gt('created_at', since.toISOString())
  }

  const { data, error } = await query

  if (error) {
    throw error
  }

  return (data ?? []) as ActivityDeltaRow[]
}
