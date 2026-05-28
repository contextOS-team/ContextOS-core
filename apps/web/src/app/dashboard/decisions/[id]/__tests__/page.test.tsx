// @vitest-environment jsdom

import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ApiNode } from '@/components/graph/types'
import DecisionDetailPage from '../page'

const apiMocks = vi.hoisted(() => ({
  fetchDecision: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  fetchDecision: apiMocks.fetchDecision,
}))

vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'decision-1' }),
}))

function decision(): ApiNode {
  return {
    id: 'decision-1',
    entity_type: 'Decision',
    name: 'Add a new button to the interface as part of the task implementation.',
    depth: 0,
    properties: {
      date: '2026-04-22',
      source: 'slack',
      source_channel: 'dev-room',
      source_link: 'https://t.me/c/3644773967/1356',
      rationale: 'The team agreed the task includes adding a specific button.',
    },
  }
}

describe('DecisionDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMocks.fetchDecision.mockResolvedValue(decision())
  })

  it('loads a decision by ID instead of searching the workspace graph subset', async () => {
    render(<DecisionDetailPage />)

    expect(
      await screen.findByText('Add a new button to the interface as part of the task implementation.')
    ).toBeTruthy()
    expect(apiMocks.fetchDecision).toHaveBeenCalledWith('decision-1')
  })

  it('renders the preserved source link for saved decision receipts', async () => {
    render(<DecisionDetailPage />)

    const sourceLink = await screen.findByRole('link', {
      name: 'Open Telegram source',
    })

    expect(sourceLink.getAttribute('href')).toBe('https://t.me/c/3644773967/1356')
    expect(sourceLink.getAttribute('target')).toBe('_blank')
  })
})
