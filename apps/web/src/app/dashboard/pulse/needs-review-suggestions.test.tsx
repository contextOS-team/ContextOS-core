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
    possible_existing_match: overrides.possible_existing_match ?? {
      match_status: 'weak_match',
      entity_type: 'Decision',
      entity_id: 'decision-77',
      title: 'Use regional rollout guardrails',
    },
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
    await saveMissedDecisionAsNewDecision('candidate-1')
    await addMissedDecisionAsEvidence('candidate-1')
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
      'http://localhost:8000/api/missed-decisions/candidate-1/confirm',
      expect.objectContaining({ method: 'POST' })
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      'http://localhost:8000/api/missed-decisions/candidate-1/add-evidence',
      expect.objectContaining({ method: 'POST' })
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      'http://localhost:8000/api/missed-decisions/candidate-1/defer',
      expect.objectContaining({ method: 'POST' })
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      'http://localhost:8000/api/missed-decisions/candidate-1/reject',
      expect.objectContaining({ method: 'POST' })
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      6,
      'http://localhost:8000/api/missed-decisions/candidate-1/ignore-duplicate',
      expect.objectContaining({ method: 'POST' })
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

  it('keeps missed-decision fetch failures local to the Needs review section', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const path = new URL(String(input)).pathname
        if (path === '/api/dashboard/attention') return Promise.resolve(makeResponse([]))
        if (path === '/api/suggestions') return Promise.resolve(makeResponse([]))
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

    expect(screen.getByText('Needs review')).toBeTruthy()
    expect(screen.getByText('Decisions found in recent syncs that need a quick call.')).toBeTruthy()
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

  it('renders source-backed candidate details and approved action labels', () => {
    render(
      <NeedsReviewSuggestions
        suggestions={[candidate()]}
        onSaveAsNewDecision={vi.fn()}
        onAddAsEvidence={vi.fn()}
        onDefer={vi.fn()}
        onDismiss={vi.fn()}
        onIgnoreDuplicate={vi.fn()}
      />
    )

    expect(screen.getByText('Use the regional rollout guardrail')).toBeTruthy()
    expect(screen.getByText(/Ship it to Region A first/)).toBeTruthy()
    expect(screen.getByText('Slack source')).toBeTruthy()
    expect(screen.getByText('high confidence')).toBeTruthy()
    expect(screen.getByText('Daulet, Vasiliy')).toBeTruthy()
    expect(screen.getByText('RegionApp')).toBeTruthy()
    expect(screen.getByText('Possible existing decision: Use regional rollout guardrails')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Save as new decision' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Add as evidence' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Defer' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Dismiss candidate' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Ignore duplicate' })).toBeTruthy()
    expect(screen.queryByText(/Link existing/i)).toBeNull()
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

    await user.click(screen.getByRole('button', { name: 'Save as new decision' }))
    await user.click(screen.getByRole('button', { name: 'Add as evidence' }))
    await user.click(screen.getByRole('button', { name: 'Defer' }))

    expect(onSaveAsNewDecision).toHaveBeenCalledWith('candidate-1')
    expect(onAddAsEvidence).toHaveBeenCalledWith('candidate-1')
    expect(onDefer).toHaveBeenCalledWith('candidate-1')

    await user.click(screen.getByRole('button', { name: 'Dismiss candidate' }))
    let dialog = await screen.findByRole('alertdialog')
    expect(within(dialog).getByText('Dismiss this candidate without creating decision memory.')).toBeTruthy()
    await user.click(within(dialog).getByRole('button', { name: 'Dismiss candidate' }))

    await waitFor(() => {
      expect(onDismiss).toHaveBeenCalledWith('candidate-1')
    })

    await user.click(screen.getByRole('button', { name: 'Ignore duplicate' }))
    dialog = await screen.findByRole('alertdialog')
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
        suggestions={[candidate()]}
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
  it('keeps Recent decisions primary and places missed-decision review in the right rail', () => {
    const source = readFileSync(
      path.join(process.cwd(), 'src/app/dashboard/page.tsx'),
      'utf8'
    )
    const recentIndex = source.indexOf('<RecentDecisions data={decisions}')
    const reviewIndex = source.indexOf('<NeedsReviewSuggestions')
    const activeContextIndex = source.indexOf('<ActiveContext')
    const needsYouIndex = source.indexOf('<NeedsYou')

    expect(recentIndex).toBeGreaterThan(-1)
    expect(reviewIndex).toBeGreaterThan(recentIndex)
    expect(activeContextIndex).toBeGreaterThan(reviewIndex)
    expect(needsYouIndex).toBeGreaterThan(activeContextIndex)
    expect(source).not.toContain('<RecentDecisions data={needsReviewSuggestions}')
  })
})
