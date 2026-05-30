// @vitest-environment jsdom

import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  addMissedDecisionAsEvidence,
  deferMissedDecision,
  dismissMissedDecision,
  getDashboardSuggestions,
  getMissedDecisionScanStatus,
  getMissedDecisionReviewSuggestions,
  ignoreMissedDecisionDuplicate,
  saveMissedDecisionAsNewDecision,
  type MissedDecisionReviewSuggestion,
} from '@/lib/api'
import { NeedsReviewSuggestions } from './needs-review-suggestions'
import { useDashboardData } from './use-dashboard-data'

const supabaseMocks = vi.hoisted(() => ({
  getSession: vi.fn(),
}))

const contextMocks = vi.hoisted(() => ({
  fetchContextPages: vi.fn(),
}))

const activityMocks = vi.hoisted(() => ({
  bucketDelta: vi.fn(),
  fetchActivityDelta: vi.fn(),
}))

vi.mock('@/lib/supabase/client', () => ({
  createClient: () => ({
    auth: {
      getSession: supabaseMocks.getSession,
    },
  }),
}))

vi.mock('@/lib/context-feed', () => ({
  fetchContextPages: contextMocks.fetchContextPages,
}))

vi.mock('./since-last-visit/activity-delta', () => ({
  bucketDelta: activityMocks.bucketDelta,
  fetchActivityDelta: activityMocks.fetchActivityDelta,
}))

function candidate(
  overrides: Partial<MissedDecisionReviewSuggestion> = {}
): MissedDecisionReviewSuggestion {
  return {
    id: overrides.id ?? 'candidate-1',
    workspace_id: overrides.workspace_id ?? 'workspace-1',
    status: 'surfaced',
    suggestion_id: 'suggestion-1',
    title: overrides.title ?? 'Use the regional rollout guardrail',
    inferred_decision: overrides.inferred_decision ?? 'Use the regional rollout guardrail',
    inferred_rationale: 'The source says the staged rollout is required before expansion.',
    source_quote: overrides.source_quote ?? 'Ship it to Region A first, then expand after support confirms.',
    source_link: overrides.source_link ?? 'https://slack.com/archives/C123/p1716211200000000',
    confidence: overrides.confidence ?? 'high',
    people: overrides.people ?? ['Daulet', 'Vasiliy'],
    affected_systems: overrides.affected_systems ?? ['RegionApp'],
    review_context: overrides.review_context ?? {
      business_category: 'deployment_timing',
      affected_object: 'RegionApp release',
      expected_artifact_type: 'deployment_checklist',
      expected_artifact: 'Deployment checklist should document the regional rollout guardrail.',
      impact_level: 'medium',
      impact_reason: 'Forgetting this would change release execution.',
      searched_sources: ['Decision memory', 'Tickets', 'PRs', 'Docs'],
    },
    actionability: overrides.actionability ?? {
      status: 'actionable',
      reason: 'No matching fresh artifact was found.',
      searched_sources: ['Decision memory', 'Tickets', 'PRs', 'Docs'],
      stale_providers: [],
      artifact_matches: [],
      next_action: {
        kind: 'attach_evidence',
        write_policy: 'review_required',
        title: 'Attach source evidence to existing decision',
        body: 'Decision: Use the regional rollout guardrail',
        source_quote: overrides.source_quote ?? 'Ship it to Region A first, then expand after support confirms.',
        source_link: overrides.source_link ?? 'https://slack.com/archives/C123/p1716211200000000',
        searched_sources: ['Decision memory', 'Tickets', 'PRs', 'Docs'],
        copyable: false,
      },
    },
    draft_action: overrides.draft_action ?? null,
    draft_title: overrides.draft_title ?? null,
    draft_body: overrides.draft_body ?? null,
    possible_existing_match: overrides.possible_existing_match ?? {
      match_status: 'weak_match',
      entity_type: 'Decision',
      entity_id: 'decision-77',
      title: 'Use regional rollout guardrails',
      href: '/dashboard/decisions/decision-77',
      match_reason: 'Similar rollout decision already exists.',
    },
    recommended_action: overrides.recommended_action ?? 'add_as_evidence',
    legal_actions: overrides.legal_actions ?? [
      'confirm',
      'add_evidence',
      'defer',
      'reject',
      'ignore_duplicate',
    ],
    ...overrides,
  }
}

function makeResponse(value: unknown): Response {
  return {
    ok: true,
    json: async () => value,
    text: async () => '',
  } as Response
}

function DashboardProbe() {
  const data = useDashboardData('workspace-1', null)

  return (
    <output data-testid="dashboard-state">
      {JSON.stringify({
        error: data.error,
        needsReviewError: data.needsReviewError,
        needsReviewSuggestions: data.needsReviewSuggestions.length,
        missedDecisionScans: data.missedDecisionScans.length,
      })}
    </output>
  )
}

describe('missed-decision API helpers', () => {
  beforeEach(() => {
    supabaseMocks.getSession.mockResolvedValue({
      data: { session: { access_token: 'token-1' } },
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it('fetches review candidates and posts actions through authenticated apiFetch routes', async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeResponse(candidate()))
    vi.stubGlobal('fetch', fetchMock)

    await getMissedDecisionReviewSuggestions()
    await getMissedDecisionScanStatus()
    await saveMissedDecisionAsNewDecision('candidate-1')
    await addMissedDecisionAsEvidence('candidate-1', 'decision-77')
    await deferMissedDecision('candidate-1')
    await dismissMissedDecision('candidate-1')
    await ignoreMissedDecisionDuplicate('candidate-1')

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8000/api/missed-decisions/review?limit=5',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer token-1' }),
      })
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'http://localhost:8000/api/missed-decisions/scans',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer token-1' }),
      })
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      'http://localhost:8000/api/missed-decisions/candidate-1/confirm',
      expect.objectContaining({ method: 'POST' })
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      'http://localhost:8000/api/missed-decisions/candidate-1/add-evidence',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ target_decision_id: 'decision-77' }),
      })
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      'http://localhost:8000/api/missed-decisions/candidate-1/defer',
      expect.objectContaining({ method: 'POST' })
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      6,
      'http://localhost:8000/api/missed-decisions/candidate-1/reject',
      expect.objectContaining({ method: 'POST' })
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      7,
      'http://localhost:8000/api/missed-decisions/candidate-1/ignore-duplicate',
      expect.objectContaining({ method: 'POST' })
    )
  })

  it('fetches generic dashboard suggestions with missed-decision exclusions', async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeResponse([]))
    vi.stubGlobal('fetch', fetchMock)

    await getDashboardSuggestions(3, { excludeTypes: ['missed_decision'] })

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/suggestions?limit=3&exclude_type=missed_decision',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer token-1' }),
      })
    )
  })
})

describe('useDashboardData missed-decision integration', () => {
  beforeEach(() => {
    supabaseMocks.getSession.mockResolvedValue({
      data: { session: { access_token: 'token-1' } },
    })
    contextMocks.fetchContextPages.mockResolvedValue([])
    activityMocks.fetchActivityDelta.mockResolvedValue([])
    activityMocks.bucketDelta.mockReturnValue({
      decisions: { count: 0, items: [] },
      sources: { count: 0, items: [] },
      needsYou: { topUrgentItem: null, items: [] },
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it('keeps missed-decision fetch failures local to the review exceptions section', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const path = new URL(String(input)).pathname
        if (path === '/api/dashboard/attention') return Promise.resolve(makeResponse([]))
        if (path === '/api/suggestions') return Promise.resolve(makeResponse([]))
        if (path === '/api/integrations/status') {
          const disconnected = {
            status: 'disconnected',
            external_name: null,
            connected_at: null,
          }
          return Promise.resolve(makeResponse({
            linear: disconnected,
            slack: disconnected,
            fathom: disconnected,
            github: disconnected,
            gitlab: disconnected,
            notion: disconnected,
            telegram: disconnected,
            jira: disconnected,
          }))
        }
        if (path === '/api/linear/sync/status') {
          return Promise.resolve(makeResponse({
            synced_teams: [],
            sync_status: null,
            tickets_synced: 0,
            tickets_count: 0,
            last_sync_at: null,
          }))
        }
        if (path === '/api/github/sync/status') {
          return Promise.resolve(makeResponse({ repo_sync_status: {}, last_sync_at: null }))
        }
        if (path === '/api/github/index/status') {
          return Promise.resolve(makeResponse({ status: 'idle', last_indexed_at: null, repos: [] }))
        }
        if (path === '/api/graph/lens/my-work') {
          return Promise.resolve(makeResponse({
            lens: 'my_work',
            clusters: [],
            all_edges: [],
            all_nodes: [],
            node_count: 0,
            edge_count: 0,
            truncated: false,
          }))
        }
        if (path === '/api/missed-decisions/review') {
          return Promise.resolve({
            ok: false,
            text: async () => 'scanner unavailable',
            json: async () => ({}),
          } as Response)
        }
        if (path === '/api/missed-decisions/scans') return Promise.resolve(makeResponse([]))
        return Promise.resolve(makeResponse([]))
      })
    )

    render(<DashboardProbe />)

    await waitFor(() => {
      const state = JSON.parse(screen.getByTestId('dashboard-state').textContent ?? '{}')

      expect(state.error).toBeNull()
      expect(state.needsReviewError).toMatch(/Could not load missed-decision suggestions/)
      expect(state.needsReviewSuggestions).toBe(0)
    })
  })
})

describe('NeedsReviewSuggestions', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('renders nothing when there are no open suggestions', () => {
    const { container } = render(
      <NeedsReviewSuggestions
        suggestions={[]}
        onSaveAsNewDecision={vi.fn()}
        onAddAsEvidence={vi.fn()}
        onDefer={vi.fn()}
        onDismiss={vi.fn()}
        onIgnoreDuplicate={vi.fn()}
      />
    )

    expect(container.textContent).toBe('')
  })

  it('renders the bounded section copy, top three default rows, and never more than five rows', () => {
    const suggestions = Array.from({ length: 6 }, (_, index) =>
      candidate({
        id: `candidate-${index + 1}`,
        inferred_decision: `Decision ${index + 1}`,
        title: `Decision ${index + 1}`,
      })
    )

    const { rerender } = render(
      <NeedsReviewSuggestions
        suggestions={suggestions}
        onSaveAsNewDecision={vi.fn()}
        onAddAsEvidence={vi.fn()}
        onDefer={vi.fn()}
        onDismiss={vi.fn()}
        onIgnoreDuplicate={vi.fn()}
      />
    )

    expect(screen.getByText('Decision actions')).toBeTruthy()
    expect(screen.getByText('Source-backed decisions with one concrete next action.')).toBeTruthy()
    expect(screen.getByText('Decision 1')).toBeTruthy()
    expect(screen.getByText('Decision 2')).toBeTruthy()
    expect(screen.getByText('Decision 3')).toBeTruthy()
    expect(screen.queryByText('Decision 4')).toBeNull()

    rerender(
      <NeedsReviewSuggestions
        suggestions={suggestions}
        limit={9}
        onSaveAsNewDecision={vi.fn()}
        onAddAsEvidence={vi.fn()}
        onDefer={vi.fn()}
        onDismiss={vi.fn()}
        onIgnoreDuplicate={vi.fn()}
      />
    )

    expect(screen.getByText('Decision 5')).toBeTruthy()
    expect(screen.queryByText('Decision 6')).toBeNull()
  })

  it('renders source-backed candidate details, recommendation, match link, and bounded actions', async () => {
    const user = userEvent.setup()
    const longQuote = 'Ship it to Region A first, then expand after support confirms. '.repeat(8)
    render(
      <NeedsReviewSuggestions
        suggestions={[candidate({ source_quote: longQuote })]}
        onSaveAsNewDecision={vi.fn()}
        onAddAsEvidence={vi.fn()}
        onDefer={vi.fn()}
        onDismiss={vi.fn()}
        onIgnoreDuplicate={vi.fn()}
      />
    )

    expect(screen.getByText('Use the regional rollout guardrail')).toBeTruthy()
    expect(screen.getByText(/Recommended action/i)).toBeTruthy()
    expect(screen.getByText(/Add as evidence/i)).toBeTruthy()
    expect(screen.getByText(/Similar rollout decision already exists/)).toBeTruthy()
    expect(screen.getByRole('link', { name: /Use regional rollout guardrails/i }).getAttribute('href'))
      .toBe('/dashboard/decisions/decision-77')
    expect(screen.getByText(/Ship it to Region A first/)).toBeTruthy()
    expect(screen.getByRole('button', { name: /Show full quote/i })).toBeTruthy()
    await user.click(screen.getByRole('button', { name: /Show full quote/i }))
    expect(screen.getByRole('button', { name: /Collapse quote/i })).toBeTruthy()
    const sourceLink = screen.getByRole('link', { name: 'Open slack source' })
    expect(sourceLink.getAttribute('href')).toBe('https://slack.com/archives/C123/p1716211200000000')
    expect(sourceLink.getAttribute('target')).toBe('_blank')
    expect(screen.getByText('high confidence')).toBeTruthy()
    expect(screen.getByText('Daulet, Vasiliy')).toBeTruthy()
    expect(screen.getByText('RegionApp')).toBeTruthy()
    expect(screen.getByText('Missing artifact')).toBeTruthy()
    expect(screen.getByText('Deployment checklist')).toBeTruthy()
    expect(screen.getByText('RegionApp release')).toBeTruthy()
    expect(screen.getByText('Decision memory, Tickets, PRs, Docs')).toBeTruthy()
    expect(screen.getByText('medium impact')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Add as evidence' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Save as new decision' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Defer' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Dismiss candidate' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Ignore duplicate' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Candidate actions' })).toBeTruthy()
    expect(screen.getByRole('link', { name: /view all/i }).getAttribute('href'))
      .toBe('/dashboard/suggestions')
    expect(screen.queryByText(/Link existing/i)).toBeNull()
  })

  it('renders draft ticket copy and copies the generated draft', async () => {
    const user = userEvent.setup()
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    })
    render(
      <NeedsReviewSuggestions
        suggestions={[
          candidate({
            possible_existing_match: {
              match_status: 'no_match',
              entity_type: null,
              entity_id: null,
              title: null,
              href: null,
              match_reason: null,
            },
            recommended_action: 'draft_ticket',
            legal_actions: ['defer', 'reject'],
            draft_title: 'Track decision: Use the regional rollout guardrail',
            draft_body: 'Decision: Use the regional rollout guardrail\n\nSource quote: "Ship it to Region A first"',
            draft_action: {
              kind: 'draft_ticket',
              write_policy: 'draft_external',
              title: 'Track decision: Use the regional rollout guardrail',
              body: 'Decision: Use the regional rollout guardrail\n\nSource quote: "Ship it to Region A first"',
              source_quote: 'Ship it to Region A first, then expand after support confirms.',
              source_link: 'https://slack.com/archives/C123/p1716211200000000',
              searched_sources: ['Decision memory', 'Tickets', 'PRs', 'Docs'],
              copyable: true,
            },
            actionability: {
              status: 'actionable',
              reason: 'No matching fresh ticket was found.',
              searched_sources: ['Decision memory', 'Tickets', 'PRs', 'Docs'],
              stale_providers: [],
              artifact_matches: [],
              next_action: {
                kind: 'draft_ticket',
                write_policy: 'draft_external',
                title: 'Track decision: Use the regional rollout guardrail',
                body: 'Decision: Use the regional rollout guardrail\n\nSource quote: "Ship it to Region A first"',
                source_quote: 'Ship it to Region A first, then expand after support confirms.',
                source_link: 'https://slack.com/archives/C123/p1716211200000000',
                searched_sources: ['Decision memory', 'Tickets', 'PRs', 'Docs'],
                copyable: true,
              },
            },
          }),
        ]}
        onSaveAsNewDecision={vi.fn()}
        onAddAsEvidence={vi.fn()}
        onDefer={vi.fn()}
        onDismiss={vi.fn()}
        onIgnoreDuplicate={vi.fn()}
      />
    )

    expect(screen.getByText('Track decision: Use the regional rollout guardrail')).toBeTruthy()
    expect(screen.getByText(/Decision: Use the regional rollout guardrail/)).toBeTruthy()
    expect(screen.getByText('Decision memory, Tickets, PRs, Docs')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Save as new decision' })).toBeNull()

    await user.click(screen.getByRole('button', { name: 'Copy draft' }))

    expect(writeText).toHaveBeenCalledWith(
      expect.stringContaining('Track decision: Use the regional rollout guardrail')
    )
  })

  it('hides stale and unsupported candidates from the Decision actions rail', () => {
    render(
      <NeedsReviewSuggestions
        suggestions={[
          candidate({
            id: 'stale-candidate',
            inferred_decision: 'Stale search candidate',
            actionability: {
              status: 'stale_search',
              reason: 'Provider is stale.',
              searched_sources: [],
              stale_providers: ['jira'],
              artifact_matches: [],
              next_action: null,
            },
          }),
          candidate({
            id: 'unsupported-candidate',
            inferred_decision: 'Unsupported candidate',
            actionability: {
              status: 'unsupported_artifact',
              reason: 'Unsupported.',
              searched_sources: [],
              stale_providers: [],
              artifact_matches: [],
              next_action: null,
            },
          }),
        ]}
        onSaveAsNewDecision={vi.fn()}
        onAddAsEvidence={vi.fn()}
        onDefer={vi.fn()}
        onDismiss={vi.fn()}
        onIgnoreDuplicate={vi.fn()}
      />
    )

    expect(screen.queryByText('Stale search candidate')).toBeNull()
    expect(screen.queryByText('Unsupported candidate')).toBeNull()
  })

  it('does not render raw matched entity ids when match title is missing', () => {
    const rawId = '353d3ff0-73df-4593-a53c-5c43f86ecb60'
    render(
      <NeedsReviewSuggestions
        suggestions={[
          candidate({
            possible_existing_match: {
              match_status: 'weak_match',
              entity_type: 'Decision',
              entity_id: rawId,
              title: null,
              href: null,
              match_reason: null,
            },
          }),
        ]}
        onSaveAsNewDecision={vi.fn()}
        onAddAsEvidence={vi.fn()}
        onDefer={vi.fn()}
        onDismiss={vi.fn()}
        onIgnoreDuplicate={vi.fn()}
      />
    )

    expect(screen.queryByText(rawId)).toBeNull()
    expect(screen.queryByText(/Possible existing decision/i)).toBeNull()
  })

  it('labels Telegram provider links directly', () => {
    render(
      <NeedsReviewSuggestions
        suggestions={[candidate({ source_link: 'https://t.me/c/3644773967/1356' })]}
        onSaveAsNewDecision={vi.fn()}
        onAddAsEvidence={vi.fn()}
        onDefer={vi.fn()}
        onDismiss={vi.fn()}
        onIgnoreDuplicate={vi.fn()}
      />
    )

    const sourceLink = screen.getByRole('link', { name: 'Open telegram source' })
    expect(sourceLink.getAttribute('href')).toBe('https://t.me/c/3644773967/1356')
  })

  it('does not offer add evidence when the existing match is not a Decision target', async () => {
    const user = userEvent.setup()
    const onAddAsEvidence = vi.fn()
    const onSaveAsNewDecision = vi.fn().mockResolvedValue(undefined)
    render(
      <NeedsReviewSuggestions
        suggestions={[
          candidate({
            possible_existing_match: {
              match_status: 'weak_match',
              entity_type: 'Ticket',
              entity_id: 'ticket-1',
              title: 'REG-123 Add rollout guardrail',
              href: 'https://linear.example/REG-123',
              match_reason: 'Ticket mentions the same rollout area.',
            },
            recommended_action: 'inspect_existing_match',
            legal_actions: ['confirm', 'add_evidence', 'defer', 'reject'],
          }),
        ]}
        onSaveAsNewDecision={onSaveAsNewDecision}
        onAddAsEvidence={onAddAsEvidence}
        onDefer={vi.fn()}
        onDismiss={vi.fn()}
        onIgnoreDuplicate={vi.fn()}
      />
    )

    expect(screen.queryByRole('button', { name: 'Add as evidence' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Save as new decision' })).toBeTruthy()

    await user.click(screen.getByRole('button', { name: 'Save as new decision' }))
    expect(onSaveAsNewDecision).toHaveBeenCalledWith('candidate-1')

    await user.click(screen.getByRole('button', { name: 'Candidate actions' }))
    expect(screen.queryByRole('menuitem', { name: 'Add as evidence' })).toBeNull()
    expect(onAddAsEvidence).not.toHaveBeenCalled()
  })

  it('calls action callbacks and confirms destructive actions before finalizing', async () => {
    const user = userEvent.setup()
    const onSaveAsNewDecision = vi.fn().mockResolvedValue(undefined)
    const onAddAsEvidence = vi.fn().mockResolvedValue(undefined)
    const onDefer = vi.fn().mockResolvedValue(undefined)
    const onDismiss = vi.fn().mockResolvedValue(undefined)
    const onIgnoreDuplicate = vi.fn().mockResolvedValue(undefined)

    render(
      <NeedsReviewSuggestions
        suggestions={[candidate()]}
        onSaveAsNewDecision={onSaveAsNewDecision}
        onAddAsEvidence={onAddAsEvidence}
        onDefer={onDefer}
        onDismiss={onDismiss}
        onIgnoreDuplicate={onIgnoreDuplicate}
      />
    )

    await user.click(screen.getByRole('button', { name: 'Add as evidence' }))

    expect(onAddAsEvidence).toHaveBeenCalledWith('candidate-1', 'decision-77')

    await user.click(screen.getByRole('button', { name: 'Candidate actions' }))
    expect(await screen.findByRole('menuitem', { name: 'Not a product decision' })).toBeTruthy()
    expect(screen.getByRole('menuitem', { name: 'Too low impact' })).toBeTruthy()
    expect(screen.getByRole('menuitem', { name: 'Wrong affected system' })).toBeTruthy()
    await user.click(await screen.findByRole('menuitem', { name: 'Save as new decision' }))
    expect(onSaveAsNewDecision).toHaveBeenCalledWith('candidate-1')

    await user.click(screen.getByRole('button', { name: 'Candidate actions' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Defer' }))
    expect(onDefer).toHaveBeenCalledWith('candidate-1')

    await user.click(screen.getByRole('button', { name: 'Candidate actions' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Dismiss candidate' }))
    let dialog = await screen.findByRole('alertdialog')
    expect(within(dialog).getByText('Dismiss this candidate without creating decision memory.')).toBeTruthy()
    await user.click(within(dialog).getByRole('button', { name: 'Dismiss candidate' }))

    await waitFor(() => {
      expect(onDismiss).toHaveBeenCalledWith('candidate-1')
    })

    await user.click(screen.getByRole('button', { name: 'Candidate actions' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Ignore duplicate' }))
    dialog = await screen.findByRole('alertdialog')
    expect(within(dialog).getByText('Keep the existing decision and hide this candidate.')).toBeTruthy()
    await user.click(within(dialog).getByRole('button', { name: 'Ignore duplicate' }))

    await waitFor(() => {
      expect(onIgnoreDuplicate).toHaveBeenCalledWith('candidate-1')
    })

    await user.click(screen.getByRole('button', { name: 'Candidate actions' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Not a product decision' }))

    await waitFor(() => {
      expect(onDismiss).toHaveBeenCalledWith(
        'candidate-1',
        'not_product_or_engineering_decision'
      )
    })
  })

  it('confirms a primary ignore duplicate action before suppressing', async () => {
    const user = userEvent.setup()
    const onIgnoreDuplicate = vi.fn().mockResolvedValue(undefined)

    render(
      <NeedsReviewSuggestions
        suggestions={[
          candidate({
            possible_existing_match: {
              match_status: 'strong_match',
              entity_type: 'missed_decision_candidate',
              entity_id: 'candidate-previous',
              title: 'Use the regional rollout guardrail',
              href: null,
              match_reason: 'Same decision was already captured.',
            },
            recommended_action: 'ignore_duplicate',
            legal_actions: ['ignore_duplicate', 'defer', 'reject'],
          }),
        ]}
        onSaveAsNewDecision={vi.fn()}
        onAddAsEvidence={vi.fn()}
        onDefer={vi.fn()}
        onDismiss={vi.fn()}
        onIgnoreDuplicate={onIgnoreDuplicate}
      />
    )

    await user.click(screen.getByRole('button', { name: 'Ignore duplicate' }))

    expect(onIgnoreDuplicate).not.toHaveBeenCalled()
    const dialog = await screen.findByRole('alertdialog')
    expect(within(dialog).getByText('Keep the existing decision and hide this candidate.')).toBeTruthy()

    await user.click(within(dialog).getByRole('button', { name: 'Ignore duplicate' }))

    await waitFor(() => {
      expect(onIgnoreDuplicate).toHaveBeenCalledWith('candidate-1')
    })
  })

  it('keeps the row visible and shows inline error copy after action failure', async () => {
    const user = userEvent.setup()

    render(
      <NeedsReviewSuggestions
        suggestions={[candidate({ recommended_action: 'save_as_new_decision' })]}
        onSaveAsNewDecision={vi.fn().mockRejectedValue(new Error('nope'))}
        onAddAsEvidence={vi.fn()}
        onDefer={vi.fn()}
        onDismiss={vi.fn()}
        onIgnoreDuplicate={vi.fn()}
      />
    )

    await act(async () => {
      await user.click(screen.getByRole('button', { name: 'Save as new decision' }))
    })

    expect(screen.getByText('Use the regional rollout guardrail')).toBeTruthy()
    expect(screen.getByText('Could not update this suggestion. Try again.')).toBeTruthy()
  })
})

describe('dashboard missed-decision composition', () => {
  it('keeps source activity and Recent decisions primary while missed-decision review stays in the right rail', () => {
    const source = readFileSync(
      path.join(process.cwd(), 'src/app/dashboard/page.tsx'),
      'utf8'
    )
    const recentIndex = source.indexOf('<RecentDecisions data={decisions}')
    const sourceUpdatesIndex = source.indexOf('<SourceUpdates')
    const snapshotIndex = source.indexOf('<WorkspaceSnapshot')
    const scanProgressIndex = source.indexOf('<DecisionScanProgress')
    const reviewIndex = source.indexOf('<NeedsReviewSuggestions')
    const activeContextIndex = source.indexOf('<ActiveContext')
    const needsYouIndex = source.indexOf('<NeedsYou')

    expect(recentIndex).toBeGreaterThan(-1)
    expect(sourceUpdatesIndex).toBeGreaterThan(recentIndex)
    expect(snapshotIndex).toBeGreaterThan(sourceUpdatesIndex)
    expect(scanProgressIndex).toBeGreaterThan(snapshotIndex)
    expect(reviewIndex).toBeGreaterThan(scanProgressIndex)
    expect(activeContextIndex).toBeGreaterThan(reviewIndex)
    expect(needsYouIndex).toBeGreaterThan(activeContextIndex)
    expect(source).not.toContain('<RecentDecisions data={needsReviewSuggestions}')
    expect(source).not.toContain(') : (\n        <NeedsReview items={suggestions} />')
  })
})
