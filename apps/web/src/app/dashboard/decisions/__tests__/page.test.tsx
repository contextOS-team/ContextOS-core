// @vitest-environment jsdom

import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ApiNode } from '@/components/graph/types'
import DecisionsPage from '../page'

const apiMocks = vi.hoisted(() => ({
  fetchDecisions: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  fetchDecisions: apiMocks.fetchDecisions,
}))

function decision(id: string, name: string, date: string): ApiNode {
  return {
    id,
    entity_type: 'Decision',
    name,
    depth: 0,
    properties: {
      date,
      source: 'slack',
      source_channel: 'dev-room',
    },
  }
}

describe('DecisionsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMocks.fetchDecisions.mockResolvedValue([
      decision('decision-1', 'Branch names must contain exactly one dash', '2026-05-22'),
      decision(
        'decision-2',
        'Use a Bottom Sheet for menu visuals in the RD-752 release',
        '2026-05-04'
      ),
      decision(
        'decision-3',
        'Add a new button to the interface as part of the task implementation.',
        '2026-04-22'
      ),
    ])
  })

  it('renders all decisions returned by the decision endpoint', async () => {
    render(<DecisionsPage />)

    expect(await screen.findByText('3 decisions from connected sources')).toBeTruthy()
    expect(screen.getByText('Use a Bottom Sheet for menu visuals in the RD-752 release')).toBeTruthy()
    expect(screen.getByText('Add a new button to the interface as part of the task implementation.')).toBeTruthy()
    expect(apiMocks.fetchDecisions).toHaveBeenCalled()
  })
})
