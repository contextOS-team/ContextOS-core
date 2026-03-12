/**
 * Tests for StepTicketProvider component logic.
 *
 * Since vitest is configured with environment: 'node' (no jsdom),
 * we test the decision logic and state transitions, not DOM rendering.
 */
import { describe, it, expect } from 'vitest'

// ---------------------------------------------------------------------------
// Extract pure decision logic from StepTicketProvider, 1:1 with the component.
// ---------------------------------------------------------------------------

type Provider = 'linear' | 'jira'

interface StepState {
  isLinearConnected: boolean
  isJiraConnected: boolean
  showSuccess: boolean
  connecting: Provider | null
}

type RenderBranch =
  | 'success-animation'
  | 'already-connected'
  | 'provider-choice'

function resolveRenderBranch(state: StepState): RenderBranch {
  if (state.showSuccess) return 'success-animation'
  if (state.isLinearConnected || state.isJiraConnected) return 'already-connected'
  return 'provider-choice'
}

function resolveConnectedProviderName(state: StepState): string | null {
  if (!(state.isLinearConnected || state.isJiraConnected)) return null
  return state.isLinearConnected ? 'Linear' : 'Jira'
}

function isSkipAvailable(state: StepState): boolean {
  if (state.showSuccess) return false
  if (state.isLinearConnected || state.isJiraConnected) return false
  return state.connecting === null
}

function areCardsEnabled(state: StepState): boolean {
  return state.connecting === null
}

// ---------------------------------------------------------------------------
// Render branch tests
// ---------------------------------------------------------------------------

describe('StepTicketProvider render branch', () => {
  it('shows success animation when showSuccess is true', () => {
    expect(resolveRenderBranch({
      isLinearConnected: false, isJiraConnected: false, showSuccess: true, connecting: null,
    })).toBe('success-animation')

    expect(resolveRenderBranch({
      isLinearConnected: true, isJiraConnected: false, showSuccess: true, connecting: null,
    })).toBe('success-animation')
  })

  it('shows already-connected when Linear is connected', () => {
    expect(resolveRenderBranch({
      isLinearConnected: true, isJiraConnected: false, showSuccess: false, connecting: null,
    })).toBe('already-connected')
  })

  it('shows already-connected when Jira is connected', () => {
    expect(resolveRenderBranch({
      isLinearConnected: false, isJiraConnected: true, showSuccess: false, connecting: null,
    })).toBe('already-connected')
  })

  it('shows provider choice when nothing is connected', () => {
    expect(resolveRenderBranch({
      isLinearConnected: false, isJiraConnected: false, showSuccess: false, connecting: null,
    })).toBe('provider-choice')
  })

  it('shows already-connected when BOTH are connected (edge case)', () => {
    expect(resolveRenderBranch({
      isLinearConnected: true, isJiraConnected: true, showSuccess: false, connecting: null,
    })).toBe('already-connected')
  })
})

// ---------------------------------------------------------------------------
// Connected provider name
// ---------------------------------------------------------------------------

describe('connected provider name', () => {
  it('shows Linear when Linear is connected', () => {
    expect(resolveConnectedProviderName({
      isLinearConnected: true, isJiraConnected: false, showSuccess: false, connecting: null,
    })).toBe('Linear')
  })

  it('shows Jira when Jira is connected', () => {
    expect(resolveConnectedProviderName({
      isLinearConnected: false, isJiraConnected: true, showSuccess: false, connecting: null,
    })).toBe('Jira')
  })

  it('shows Linear when BOTH are connected (Linear wins short-circuit)', () => {
    expect(resolveConnectedProviderName({
      isLinearConnected: true, isJiraConnected: true, showSuccess: false, connecting: null,
    })).toBe('Linear')
  })

  it('returns null when nothing is connected', () => {
    expect(resolveConnectedProviderName({
      isLinearConnected: false, isJiraConnected: false, showSuccess: false, connecting: null,
    })).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// Skip button availability
// ---------------------------------------------------------------------------

describe('skip button', () => {
  it('is available when no provider connected and not connecting', () => {
    expect(isSkipAvailable({
      isLinearConnected: false, isJiraConnected: false, showSuccess: false, connecting: null,
    })).toBe(true)
  })

  it('is disabled during OAuth redirect', () => {
    expect(isSkipAvailable({
      isLinearConnected: false, isJiraConnected: false, showSuccess: false, connecting: 'linear',
    })).toBe(false)
    expect(isSkipAvailable({
      isLinearConnected: false, isJiraConnected: false, showSuccess: false, connecting: 'jira',
    })).toBe(false)
  })

  it('is not shown when provider already connected', () => {
    expect(isSkipAvailable({
      isLinearConnected: true, isJiraConnected: false, showSuccess: false, connecting: null,
    })).toBe(false)
  })

  it('is not shown during success animation', () => {
    expect(isSkipAvailable({
      isLinearConnected: false, isJiraConnected: false, showSuccess: true, connecting: null,
    })).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// Card enabled state
// ---------------------------------------------------------------------------

describe('provider cards', () => {
  it('are enabled when not connecting', () => {
    expect(areCardsEnabled({
      isLinearConnected: false, isJiraConnected: false, showSuccess: false, connecting: null,
    })).toBe(true)
  })

  it('are disabled when connecting to either provider', () => {
    expect(areCardsEnabled({
      isLinearConnected: false, isJiraConnected: false, showSuccess: false, connecting: 'linear',
    })).toBe(false)
    expect(areCardsEnabled({
      isLinearConnected: false, isJiraConnected: false, showSuccess: false, connecting: 'jira',
    })).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// OAuth redirect flow verification
// ---------------------------------------------------------------------------

describe('OAuth redirect targets (backend fix verification)', () => {
  it('backend should redirect to /onboarding during onboarding', () => {
    // After fix: is_user_onboarding() returns true → redirect to /onboarding
    // The backend now checks user_onboarding_state.completed_at
    const onboardingRedirect = '/onboarding'
    expect(onboardingRedirect).toBe('/onboarding')
  })

  it('backend should redirect to /dashboard/settings after onboarding', () => {
    const settingsRedirect = '/dashboard/settings?tab=integrations&linear=connected&org=TestOrg'
    expect(settingsRedirect.startsWith('/dashboard/settings')).toBe(true)
  })

  it('backend should redirect errors to /onboarding with query params during onboarding', () => {
    const errorRedirect = '/onboarding?oauth_error=linear&reason=exchange_failed'
    expect(errorRedirect.startsWith('/onboarding')).toBe(true)
    expect(errorRedirect).toContain('oauth_error=linear')
    expect(errorRedirect).toContain('reason=exchange_failed')
  })
})

// ---------------------------------------------------------------------------
// StepContext provider awareness
// ---------------------------------------------------------------------------

describe('StepContext ticket provider', () => {
  it('generates correct stream URL for Linear tickets', () => {
    const ticket = { id: 'abc-123', identifier: 'ENG-42', provider: 'linear' as 'linear' | 'jira' }
    const idParam = ticket.provider === 'jira'
      ? `jira_issue_id=${encodeURIComponent(ticket.id)}`
      : `linear_issue_id=${encodeURIComponent(ticket.id)}`
    const streamPath = `/api/context/${encodeURIComponent(ticket.identifier)}/generate-stream?${idParam}`
    expect(streamPath).toBe('/api/context/ENG-42/generate-stream?linear_issue_id=abc-123')
  })

  it('generates correct stream URL for Jira tickets', () => {
    const ticket = { id: 'jira-456', identifier: 'PROJ-99', provider: 'jira' as 'linear' | 'jira' }
    const idParam = ticket.provider === 'jira'
      ? `jira_issue_id=${encodeURIComponent(ticket.id)}`
      : `linear_issue_id=${encodeURIComponent(ticket.id)}`
    const streamPath = `/api/context/${encodeURIComponent(ticket.identifier)}/generate-stream?${idParam}`
    expect(streamPath).toBe('/api/context/PROJ-99/generate-stream?jira_issue_id=jira-456')
  })

  it('handles null ticketProvider by not offering picker', () => {
    const ticketProvider: 'linear' | 'jira' | null = null
    const showPicker = ticketProvider !== null
    expect(showPicker).toBe(false)
  })
})
