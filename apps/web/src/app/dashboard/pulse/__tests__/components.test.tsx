// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ApiNode } from '@/components/graph/types'
import type { SuggestionItem } from '@/lib/api'
import { Headline } from '../headline'
import { ActiveContext } from '../active-context'
import { NeedsYou } from '../needs-you'
import { NeedsReview } from '../needs-review'
import { RecentDecisions } from '../recent-decisions'
import { SeenItemsProvider } from '../since-last-visit/use-session-seen-items'
import { SourceUpdates } from '../source-updates'
import type { Delta, NeedsYouItem } from '../types'
import { WorkspaceSnapshot } from '../workspace-snapshot'

const apiMocks = vi.hoisted(() => ({
  dismissSuggestion: vi.fn(),
  snoozeSuggestion: vi.fn(),
  resolveSuggestion: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  dismissSuggestion: apiMocks.dismissSuggestion,
  snoozeSuggestion: apiMocks.snoozeSuggestion,
  resolveSuggestion: apiMocks.resolveSuggestion,
}))

const deltaWithTuesdayNeed: Delta = {
  decisions: { count: 1, items: [{ id: 'd1', createdAt: '2026-05-20T12:00:00Z' }] },
  sources: {
    count: 1,
    items: [{
      id: 's1',
      eventType: 'sync_completed',
      createdAt: '2026-05-20T12:00:00Z',
      metadata: { integration: 'linear', items_count: 12 },
    }],
  },
  needsYou: {
    topUrgentItem: { person: 'Vasiliy', ticketId: 'RD-781', sinceDay: 'Tuesday' },
    items: [],
  },
}

const graphWithQuote: ApiNode[] = [
  {
    id: 'decision-1',
    entity_type: 'Decision',
    name: 'Use old estimate',
    depth: 0,
    properties: {
      date: '2026-05-20T10:00:00Z',
      source_quote: 'Use old estimate for now.',
      author_name: 'Daulet',
      source_channel: '#dev-room',
      participants: ['Daulet', 'Vasiliy'],
    },
  },
]

const graphWithNewlyCapturedDecision = {
  newCapture: {
    id: 'decision-new-capture',
    entity_type: 'Decision',
    name: 'Captured old source decision',
    depth: 0,
    created_at: '2026-05-20T11:00:00Z',
    properties: {
      date: '2026-05-16T10:00:00Z',
      author_name: 'Daulet',
      source_channel: '#dev-room',
    },
  },
  oldCapture: {
    id: 'decision-old-capture',
    entity_type: 'Decision',
    name: 'Older capture with newer source date',
    depth: 0,
    created_at: '2026-05-18T10:00:00Z',
    properties: {
      date: '2026-05-19T10:00:00Z',
      author_name: 'Daulet',
      source_channel: '#dev-room',
    },
  },
} satisfies Record<string, ApiNode>

function renderWithSeenProvider(ui: React.ReactElement) {
  return render(<SeenItemsProvider>{ui}</SeenItemsProvider>)
}

function suggestion(overrides: Partial<SuggestionItem> = {}): SuggestionItem {
  return {
    id: overrides.id ?? 'suggestion-1',
    workspace_id: 'workspace-1',
    type: 'missing_source_coverage',
    status: 'open',
    priority: 'medium',
    fingerprint: 'missing-source:1',
    entity_type: 'graph_node',
    entity_id: 'decision-1',
    title: overrides.title ?? 'Review design evidence for onboarding',
    body: overrides.body ?? 'Slack evidence exists, but no design review is linked.',
    primary_action: 'Review evidence',
    action_href: '/dashboard/suggestions',
    evidence: { present_evidence: ['Slack'], missing_evidence: ['design_review'] },
    details: {
      decision_title: 'onboarding',
      coverage_assessment: {
        reason: 'The decision changes a user-facing setup checklist.',
        confidence: 0.92,
        should_suggest: true,
      },
    },
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

describe('pulse components', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('flows full weekday names through the headline template', () => {
    render(<Headline delta={deltaWithTuesdayNeed} lastVisitedAt={new Date('2026-05-20T00:00:00Z')} />)

    const headline = screen.getByRole('heading', { level: 1 }).textContent ?? ''
    expect(headline).toContain('has been waiting on')
    expect(headline).toContain('since Tuesday')
    expect(screen.getByText(/source update since your last visit/i)).toBeTruthy()
  })

  it('hides Needs you when there are no items', () => {
    const { container } = renderWithSeenProvider(<NeedsYou items={[]} lastVisitedAt={null} />)

    expect(container.textContent).toBe('')
  })

  it('hides Needs review when there are no visible suggestions', () => {
    const { container } = render(<NeedsReview items={[]} />)

    expect(container.textContent).toBe('')
  })

  it('hides Recent decisions when graph data is absent', () => {
    const { container } = renderWithSeenProvider(<RecentDecisions data={null} lastVisitedAt={null} />)

    expect(container.textContent).toBe('')
  })

  it('renders a compact workspace snapshot for first-run imported data', () => {
    render(
      <WorkspaceSnapshot
        items={[
          {
            id: 'linear',
            label: 'Linear',
            value: '64',
            detail: 'tickets imported',
          },
          {
            id: 'github-code',
            label: 'GitHub',
            value: '3,053',
            detail: 'code chunks indexed',
          },
        ]}
      />
    )

    expect(screen.getByText('Workspace snapshot')).toBeTruthy()
    expect(screen.getByText('64')).toBeTruthy()
    expect(screen.getByText('tickets imported')).toBeTruthy()
    expect(screen.getByText('3,053')).toBeTruthy()
    expect(screen.getByText('code chunks indexed')).toBeTruthy()
  })

  it('renders source updates as primary dashboard content', () => {
    render(
      <SourceUpdates
        items={[
          {
            id: 'source-1',
            eventType: 'sync_completed',
            createdAt: '2026-05-20T12:00:00Z',
            metadata: { integration: 'github', items_count: 2 },
          },
          {
            id: 'source-2',
            eventType: 'integration_connected',
            createdAt: '2026-05-20T11:00:00Z',
            metadata: { integration: 'telegram', chat_title: 'contextOS team' },
          },
        ]}
      />
    )

    expect(screen.getByText('Source updates')).toBeTruthy()
    expect(screen.getByText('Latest imported activity since your last visit.')).toBeTruthy()
    expect(screen.getByText('GitHub sync completed')).toBeTruthy()
    expect(screen.getByText('2 pull requests imported.')).toBeTruthy()
    expect(screen.getByText('Telegram connected')).toBeTruthy()
    expect(screen.getByText('contextOS team is now available as a source.')).toBeTruthy()
    expect(screen.getAllByRole('link', { name: /activity/i })[0].getAttribute('href'))
      .toBe('/dashboard/activity')
  })

  it('tolerates legacy graph-shaped decision data during refresh', () => {
    const legacyData = { all_nodes: graphWithQuote } as unknown as ApiNode[]

    renderWithSeenProvider(
      <RecentDecisions
        data={legacyData}
        lastVisitedAt={new Date('2026-05-19T00:00:00Z')}
      />
    )

    expect(screen.getByRole('link', { name: /Use old estimate/ }).getAttribute('href'))
      .toBe('/dashboard/decisions/decision-1')
  })

  it('renders decision provenance quotes when source_quote exists', () => {
    renderWithSeenProvider(<RecentDecisions data={graphWithQuote} lastVisitedAt={new Date('2026-05-19T00:00:00Z')} />)

    expect(screen.getByText('Recent decisions')).toBeTruthy()
    expect(screen.getByText(/Use old estimate for now/)).toBeTruthy()
    expect(screen.getAllByText(/Daulet/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/#dev-room/).length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: /Use old estimate/ }).getAttribute('href'))
      .toBe('/dashboard/decisions/decision-1')
    expect(screen.getByRole('link', { name: /view all/i }).getAttribute('href'))
      .toBe('/dashboard/decisions')
  })

  it('keeps candidate-like unconfirmed decisions out of Recent decisions', () => {
    const unconfirmedCandidate = {
      id: 'candidate-node',
      entity_type: 'Decision',
      name: 'Candidate-like decision',
      depth: 0,
      created_at: '2026-05-20T12:00:00Z',
      properties: {
        status: 'candidate',
        source_quote: 'This is still only a candidate.',
      },
    } satisfies ApiNode
    const confirmed = {
      id: 'confirmed-node',
      entity_type: 'Decision',
      name: 'Confirmed decision',
      depth: 0,
      created_at: '2026-05-19T12:00:00Z',
      properties: {
        status: 'confirmed',
        source_quote: 'This is confirmed.',
      },
    } satisfies ApiNode
    const active = {
      id: 'active-node',
      entity_type: 'Decision',
      name: 'Active extracted decision',
      depth: 0,
      created_at: '2026-05-20T11:00:00Z',
      properties: {
        status: 'active',
        source_quote: 'This normal extracted decision is active.',
      },
    } satisfies ApiNode
    const legacy = {
      id: 'legacy-node',
      entity_type: 'Decision',
      name: 'Legacy confirmed decision',
      depth: 0,
      created_at: '2026-05-18T12:00:00Z',
      properties: {
        source_quote: 'Legacy decisions did not carry a status property.',
      },
    } satisfies ApiNode

    renderWithSeenProvider(
      <RecentDecisions
        data={[unconfirmedCandidate, active, confirmed, legacy]}
        lastVisitedAt={null}
      />
    )

    expect(screen.queryByText('Candidate-like decision')).toBeNull()
    expect(screen.getByText('Active extracted decision')).toBeTruthy()
    expect(screen.getByText('Confirmed decision')).toBeTruthy()
    expect(screen.queryByText('Legacy confirmed decision')).toBeNull()
  })

  it('prioritizes decisions captured since the last visit over older capture rows', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-05-20T12:00:00Z'))

    renderWithSeenProvider(
      <RecentDecisions
        data={[
          graphWithNewlyCapturedDecision.newCapture,
          graphWithNewlyCapturedDecision.oldCapture,
        ]}
        lastVisitedAt={new Date('2026-05-20T00:00:00Z')}
      />
    )

    const decisionLinks = screen.getAllByRole('link').filter((link) => (
      link.getAttribute('href')?.startsWith('/dashboard/decisions/')
    ))
    expect(decisionLinks[0].textContent).toContain('Captured old source decision')
    expect(decisionLinks[0].textContent).toContain('1h ago')
  })

  it('renders Active context as an artifact card with bracket tags', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-05-20T12:00:00Z'))

    renderWithSeenProvider(
      <ActiveContext
        lastVisitedAt={new Date('2026-05-19T00:00:00Z')}
        items={[
          {
            id: 'ctx-1',
            title: '[ClientApp][iOS] Pickup point',
            ticket_identifier: 'RD-302',
            status: 'ready',
            sources: [{ type: 'slack_message', id: 'm1', title: 'source', relevance_score: 1 }],
            updated_at: '2026-05-20T10:00:00Z',
            generated_at: '2026-05-20T10:00:00Z',
          },
        ]}
      />
    )

    expect(screen.getByText('Active context')).toBeTruthy()
    expect(screen.getByText('ClientApp')).toBeTruthy()
    expect(screen.getByText('iOS')).toBeTruthy()
    expect(screen.getByText('Pickup point')).toBeTruthy()
    expect(screen.getByText('1 source')).toBeTruthy()
  })

  it('demotes old context rows instead of labeling them active', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-05-21T12:00:00Z'))

    renderWithSeenProvider(
      <ActiveContext
        lastVisitedAt={new Date('2026-05-19T00:00:00Z')}
        items={[
          {
            id: 'ctx-1',
            title: '[ClientApp][iOS] Classification setup',
            ticket_identifier: 'RD-781',
            status: 'ready',
            sources: [{ type: 'slack_message', id: 'm1', title: 'source', relevance_score: 1 }],
            updated_at: '2026-04-28T10:00:00Z',
            generated_at: '2026-04-28T10:00:00Z',
          },
        ]}
      />
    )

    expect(screen.queryByText('Active context')).toBeNull()
    expect(screen.getByText('Context to revisit')).toBeTruthy()
    expect(screen.getByText('dormant')).toBeTruthy()
  })

  it('keeps dormant rows out of Active context when fresher context exists', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-05-21T12:00:00Z'))

    renderWithSeenProvider(
      <ActiveContext
        lastVisitedAt={new Date('2026-05-19T00:00:00Z')}
        items={[
          {
            id: 'ctx-1',
            title: '[ClientApp][iOS] Fresh classification setup',
            ticket_identifier: 'RD-781',
            status: 'ready',
            sources: [{ type: 'slack_message', id: 'm1', title: 'source', relevance_score: 1 }],
            updated_at: '2026-05-20T10:00:00Z',
            generated_at: '2026-05-20T10:00:00Z',
          },
          {
            id: 'ctx-2',
            title: '[ClientApp][iOS] Dormant pickup point',
            ticket_identifier: 'RD-302',
            status: 'ready',
            sources: [{ type: 'slack_message', id: 'm2', title: 'source', relevance_score: 1 }],
            updated_at: '2026-04-28T10:00:00Z',
            generated_at: '2026-04-28T10:00:00Z',
          },
        ]}
      />
    )

    expect(screen.getByText('Active context')).toBeTruthy()
    expect(screen.getByText('Fresh classification setup')).toBeTruthy()
    expect(screen.queryByText('Dormant pickup point')).toBeNull()
    expect(screen.getByText('1 older context item hidden')).toBeTruthy()
  })

  it('renders compact Needs you rows with the supplied sinceDay string', () => {
    const items: NeedsYouItem[] = [{
      id: 'need-1',
      ticketId: 'RD-781',
      person: 'Vasiliy',
      sinceDay: 'Tuesday',
      assignedToCurrentUser: true,
      ageMs: 86_400_000,
    }]

    renderWithSeenProvider(<NeedsYou items={items} lastVisitedAt={new Date('2026-05-19T00:00:00Z')} />)

    expect(screen.getByText('Needs you')).toBeTruthy()
    expect(screen.getByText(/Vasiliy asked Tuesday/)).toBeTruthy()
  })

  it('renders Needs review as a bounded right-rail section', () => {
    const items = [
      suggestion({ id: 's1', title: 'Review design evidence for onboarding' }),
      suggestion({ id: 's2', title: 'Review design evidence for pricing' }),
      suggestion({ id: 's3', title: 'Review design evidence for mobile' }),
      suggestion({ id: 's4', title: 'Review design evidence for growth' }),
    ]

    render(<NeedsReview items={items} />)

    expect(screen.getByText('Needs review')).toBeTruthy()
    expect(screen.getByText('Review design evidence for onboarding')).toBeTruthy()
    expect(screen.getByText('Review design evidence for pricing')).toBeTruthy()
    expect(screen.queryByText('Review design evidence for mobile')).toBeNull()
    expect(screen.queryByText('Review design evidence for growth')).toBeNull()
    expect(screen.getByRole('link', { name: /view all/i }).getAttribute('href'))
      .toBe('/dashboard/suggestions')
    expect(screen.queryByText('missing figma')).toBeNull()
    expect(screen.getAllByText('Has Slack').length).toBe(2)
    expect(screen.getAllByText('Missing design review').length).toBe(2)
    expect(screen.getAllByText('The decision changes a user-facing setup checklist.').length).toBe(2)
    expect(screen.getByRole('link', { name: 'Review design evidence for onboarding' }).getAttribute('href'))
      .toBe('/dashboard/decisions/decision-1')
    expect(screen.getAllByRole('link', { name: 'Review' }).length).toBe(2)
    expect(screen.getAllByRole('link', { name: 'Review' })[0].getAttribute('href'))
      .toBe('/dashboard/decisions/decision-1')
    expect(screen.queryByRole('button', { name: 'Snooze' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Mark resolved' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Dismiss' })).toBeNull()
  })

  it('normalizes stale missing-source actions to evidence review', () => {
    render(
      <NeedsReview
        items={[
          suggestion({
            action_href: '/dashboard/decisions/missing-decision',
            primary_action: 'Review gap',
          }),
        ]}
      />
    )

    expect(screen.queryByRole('link', { name: 'Review gap' })).toBeNull()
    expect(screen.getByRole('link', { name: 'Review' }).getAttribute('href'))
      .toBe('/dashboard/decisions/decision-1')
  })

  it('dismisses a suggestion through the authenticated API helper', async () => {
    apiMocks.dismissSuggestion.mockResolvedValue(suggestion({ status: 'dismissed' }))
    const user = userEvent.setup()

    render(<NeedsReview items={[suggestion()]} />)

    await user.click(screen.getByRole('button', { name: 'Suggestion actions' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Dismiss' }))

    await waitFor(() => {
      expect(apiMocks.dismissSuggestion).toHaveBeenCalledWith('suggestion-1')
      expect(screen.queryByText('Review design evidence for onboarding')).toBeNull()
    })
  })
})
