import { describe, expect, it } from 'vitest'
import type { SuggestionItem } from '../api'
import { suggestionAction } from '../suggestions'

function suggestion(overrides: Partial<SuggestionItem> = {}): SuggestionItem {
  return {
    id: 'suggestion-1',
    workspace_id: 'workspace-1',
    type: 'missing_source_coverage',
    status: 'open',
    priority: 'medium',
    fingerprint: 'missing-source:1',
    entity_type: 'graph_node',
    entity_id: 'decision/one',
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

describe('suggestionAction', () => {
  it('routes missing-source review actions to the related decision', () => {
    expect(suggestionAction(suggestion())).toEqual({
      href: '/dashboard/decisions/decision%2Fone',
      label: 'Review',
    })
  })

  it('does not create a self-link when a missing-source suggestion has no entity', () => {
    expect(suggestionAction(suggestion({ entity_id: null }))).toBeNull()
  })
})
