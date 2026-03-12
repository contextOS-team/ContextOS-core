import { describe, it, expect } from 'vitest'
import type { IntegrationStatusResponse, ProviderStatus } from '../api'
import { detectTicketProvider, ticketProviderDisabledReason } from '../ticket-provider'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const DISCONNECTED: ProviderStatus = {
  status: 'disconnected',
  external_name: null,
  connected_at: null,
}

const CONNECTED: ProviderStatus = {
  status: 'connected',
  external_name: 'test-workspace',
  connected_at: '2026-03-10T00:00:00Z',
}

const ERROR: ProviderStatus = {
  status: 'error',
  external_name: null,
  connected_at: null,
}

function makeStatuses(
  overrides: Partial<IntegrationStatusResponse> = {},
): IntegrationStatusResponse {
  return {
    linear: DISCONNECTED,
    jira: DISCONNECTED,
    slack: DISCONNECTED,
    fathom: DISCONNECTED,
    github: DISCONNECTED,
    gitlab: DISCONNECTED,
    notion: DISCONNECTED,
    telegram: DISCONNECTED,
    ...overrides,
  }
}

// ---------------------------------------------------------------------------
// detectTicketProvider
// ---------------------------------------------------------------------------

describe('detectTicketProvider', () => {
  it('returns null when neither is connected', () => {
    expect(detectTicketProvider(makeStatuses())).toBeNull()
  })

  it('returns "linear" when only Linear is connected', () => {
    expect(detectTicketProvider(makeStatuses({ linear: CONNECTED }))).toBe('linear')
  })

  it('returns "jira" when only Jira is connected', () => {
    expect(detectTicketProvider(makeStatuses({ jira: CONNECTED }))).toBe('jira')
  })

  it('returns "jira" when both are connected (deterministic tiebreaker)', () => {
    // This state shouldn't happen in normal usage, but if it does,
    // the function must be deterministic — Jira wins.
    expect(
      detectTicketProvider(makeStatuses({ linear: CONNECTED, jira: CONNECTED })),
    ).toBe('jira')
  })

  it('returns null when Linear is in error state and Jira is disconnected', () => {
    expect(detectTicketProvider(makeStatuses({ linear: ERROR }))).toBeNull()
  })

  it('returns "jira" when Linear is in error and Jira is connected', () => {
    expect(
      detectTicketProvider(makeStatuses({ linear: ERROR, jira: CONNECTED })),
    ).toBe('jira')
  })

  it('returns "linear" when Jira is in error and Linear is connected', () => {
    expect(
      detectTicketProvider(makeStatuses({ jira: ERROR, linear: CONNECTED })),
    ).toBe('linear')
  })
})

// ---------------------------------------------------------------------------
// ticketProviderDisabledReason
// ---------------------------------------------------------------------------

describe('ticketProviderDisabledReason', () => {
  it('Linear is not disabled when nothing is connected', () => {
    expect(ticketProviderDisabledReason('linear', makeStatuses())).toBeNull()
  })

  it('Jira is not disabled when nothing is connected', () => {
    expect(ticketProviderDisabledReason('jira', makeStatuses())).toBeNull()
  })

  it('Linear is disabled when Jira is connected', () => {
    const reason = ticketProviderDisabledReason(
      'linear',
      makeStatuses({ jira: CONNECTED }),
    )
    expect(reason).toBe('Disconnect Jira to switch')
  })

  it('Jira is disabled when Linear is connected', () => {
    const reason = ticketProviderDisabledReason(
      'jira',
      makeStatuses({ linear: CONNECTED }),
    )
    expect(reason).toBe('Disconnect Linear to switch')
  })

  it('Linear is not disabled when Linear itself is connected', () => {
    expect(
      ticketProviderDisabledReason('linear', makeStatuses({ linear: CONNECTED })),
    ).toBeNull()
  })

  it('Jira is not disabled when Jira itself is connected', () => {
    expect(
      ticketProviderDisabledReason('jira', makeStatuses({ jira: CONNECTED })),
    ).toBeNull()
  })

  it('Jira is not disabled when Linear is in error (not connected)', () => {
    expect(
      ticketProviderDisabledReason('jira', makeStatuses({ linear: ERROR })),
    ).toBeNull()
  })

  // Edge case: both connected — Jira should NOT be disabled (it's the winner),
  // but Linear SHOULD be disabled.
  it('both connected: Linear is disabled, Jira is not', () => {
    const both = makeStatuses({ linear: CONNECTED, jira: CONNECTED })
    expect(ticketProviderDisabledReason('linear', both)).toBe('Disconnect Jira to switch')
    expect(ticketProviderDisabledReason('jira', both)).toBe('Disconnect Linear to switch')
  })
})
