// @vitest-environment jsdom

import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { SuggestionItem } from '@/lib/api'
import SuggestionsPage from '../page'

const apiMocks = vi.hoisted(() => ({
  dismissSuggestion: vi.fn(),
  getAllSuggestions: vi.fn(),
  reopenSuggestion: vi.fn(),
  resolveSuggestion: vi.fn(),
  snoozeSuggestion: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  dismissSuggestion: apiMocks.dismissSuggestion,
  getAllSuggestions: apiMocks.getAllSuggestions,
  reopenSuggestion: apiMocks.reopenSuggestion,
  resolveSuggestion: apiMocks.resolveSuggestion,
  snoozeSuggestion: apiMocks.snoozeSuggestion,
}))

function suggestion(overrides: Partial<SuggestionItem> = {}): SuggestionItem {
  return {
    id: 'suggestion-1',
    workspace_id: 'workspace-1',
    type: 'missing_source_coverage',
    status: 'open',
    priority: 'medium',
    fingerprint: 'missing-source:1',
    entity_type: 'graph_node',
    entity_id: 'decision-1',
    title: 'Review design evidence for onboarding',
    body: 'Slack evidence exists, but no design review is linked.',
    primary_action: 'Review evidence',
    action_href: '/dashboard/suggestions',
    evidence: {},
    details: {},
    provenance: {},
    snoozed_until: null,
    dismissed_at: null,
    resolved_at: null,
    reopened_at: null,
    last_seen_at: null,
    created_at: null,
    updated_at: null,
    ...overrides,
  }
}

describe('SuggestionsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMocks.getAllSuggestions.mockResolvedValue([suggestion()])
  })

  it('renders Review as a link to the related decision', async () => {
    render(<SuggestionsPage />)

    const reviewLink = await screen.findByRole('link', { name: 'Review' })
    const titleLink = screen.getByRole('link', {
      name: 'Review design evidence for onboarding',
    })

    expect(screen.queryByRole('link', { name: 'Review evidence' })).toBeNull()
    expect(titleLink.getAttribute('href')).toBe('/dashboard/decisions/decision-1')
    expect(reviewLink.getAttribute('href')).toBe('/dashboard/decisions/decision-1')
  })
})
