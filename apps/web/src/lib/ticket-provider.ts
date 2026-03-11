/**
 * Ticket provider selection logic.
 *
 * Centralises the "Linear OR Jira" mutual-exclusion rules so they can be
 * tested without a DOM and reused across settings, onboarding, and the
 * context-page ticket picker.
 */

import type { IntegrationStatusResponse } from './api'

export type TicketProvider = 'linear' | 'jira'

/**
 * Derive which ticket provider is active from integration statuses.
 *
 * Rules:
 *  - If Jira is connected → 'jira'
 *  - Else if Linear is connected → 'linear'
 *  - Else → null (nothing connected)
 *
 * At most one should be connected at a time (enforced by the UI), but if
 * both are somehow connected, Jira wins. This is a deterministic tiebreaker,
 * not a product decision — the UI should prevent this state.
 */
export function detectTicketProvider(
  statuses: IntegrationStatusResponse,
): TicketProvider | null {
  if (statuses.jira.status === 'connected') return 'jira'
  if (statuses.linear.status === 'connected') return 'linear'
  return null
}

/**
 * Determine whether a given ticket provider card should be disabled.
 *
 * A provider is disabled when the *other* provider is already connected.
 * Returns the reason string (for display) or null if not disabled.
 */
export function ticketProviderDisabledReason(
  provider: TicketProvider,
  statuses: IntegrationStatusResponse,
): string | null {
  if (provider === 'linear' && statuses.jira.status === 'connected') {
    return 'Disconnect Jira to switch'
  }
  if (provider === 'jira' && statuses.linear.status === 'connected') {
    return 'Disconnect Linear to switch'
  }
  return null
}
