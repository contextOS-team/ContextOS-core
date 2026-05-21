// @vitest-environment jsdom

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { LensGraphResponse } from '@/components/graph/types'
import { Headline } from '../headline'
import { ActiveContext } from '../active-context'
import { NeedsYou } from '../needs-you'
import { RecentDecisions } from '../recent-decisions'
import { SeenItemsProvider } from '../since-last-visit/use-session-seen-items'
import type { Delta, NeedsYouItem } from '../types'

const deltaWithTuesdayNeed: Delta = {
  decisions: { count: 1, items: [{ id: 'd1', createdAt: '2026-05-20T12:00:00Z' }] },
  sources: { count: 1, items: [{ id: 's1', createdAt: '2026-05-20T12:00:00Z' }] },
  needsYou: {
    topUrgentItem: { person: 'Vasiliy', ticketId: 'RD-781', sinceDay: 'Tuesday' },
    items: [],
  },
}

const graphWithQuote: LensGraphResponse = {
  lens: 'my_work',
  clusters: [],
  all_edges: [],
  all_nodes: [
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
  ],
  node_count: 1,
  edge_count: 0,
  truncated: false,
}

function renderWithSeenProvider(ui: React.ReactElement) {
  return render(<SeenItemsProvider>{ui}</SeenItemsProvider>)
}

describe('pulse components', () => {
  it('flows full weekday names through the headline template', () => {
    render(<Headline delta={deltaWithTuesdayNeed} lastVisitedAt={new Date('2026-05-20T00:00:00Z')} />)

    const headline = screen.getByRole('heading', { level: 1 }).textContent ?? ''
    expect(headline).toContain('is waiting on')
    expect(headline).toContain('since Tuesday')
  })

  it('hides Needs you when there are no items', () => {
    const { container } = renderWithSeenProvider(<NeedsYou items={[]} lastVisitedAt={null} />)

    expect(container.textContent).toBe('')
  })

  it('hides Recent decisions when graph data is absent', () => {
    const { container } = renderWithSeenProvider(<RecentDecisions data={null} lastVisitedAt={null} />)

    expect(container.textContent).toBe('')
  })

  it('renders decision provenance quotes when source_quote exists', () => {
    renderWithSeenProvider(<RecentDecisions data={graphWithQuote} lastVisitedAt={new Date('2026-05-19T00:00:00Z')} />)

    expect(screen.getByText('Recent decisions')).toBeTruthy()
    expect(screen.getByText(/Use old estimate for now/)).toBeTruthy()
    expect(screen.getAllByText(/Daulet/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/#dev-room/).length).toBeGreaterThan(0)
  })

  it('renders Active context as a typographic list with bracket prefix support', () => {
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
    expect(screen.getByText('[ClientApp][iOS]')).toBeTruthy()
    expect(screen.getByText('Pickup point')).toBeTruthy()
    expect(screen.getByText('1 source')).toBeTruthy()
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
})
