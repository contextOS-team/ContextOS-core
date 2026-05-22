// @vitest-environment jsdom

import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import Hero from '../Hero'

vi.mock('posthog-js/react', () => ({
  usePostHog: () => ({
    capture: vi.fn(),
  }),
}))

describe('landing hero', () => {
  it('renders the approved decision-memory hero copy and anchors', () => {
    render(<Hero />)

    expect(screen.getByText('Early access for engineering teams')).toBeTruthy()
    expect(
      screen.getByRole('heading', {
        name: 'Know why your company works the way it does.',
      })
    ).toBeTruthy()
    expect(
      screen.getByText(
        'ContextOS finds decisions buried across Slack, meetings, GitHub/GitLab, docs, and tickets, then maps what was decided, who was involved, why it was decided, and the original source.'
      )
    ).toBeTruthy()
    expect(
      screen.getByText(
        'Decision memory for engineering teams shipping through Slack, GitHub/GitLab, Jira/Linear, Notion, Telegram, and meetings.'
      )
    ).toBeTruthy()

    const primaryLink = screen.getByRole('link', {
      name: 'See your decision graph',
    })
    expect(primaryLink.getAttribute('href')).toBe('#booking')

    const secondaryLink = screen.getByRole('link', {
      name: 'View a sample trail',
    })
    expect(secondaryLink.getAttribute('href')).toBe('#decision-trail')
  })

  it('renders the source-backed Decision Receipt proof fields', () => {
    render(<Hero />)

    expect(screen.getByText('Decision Receipt')).toBeTruthy()
    expect(screen.getByText('Verified')).toBeTruthy()
    expect(screen.getByText('Why')).toBeTruthy()
    expect(screen.getByText('People involved')).toBeTruthy()
    expect(screen.getByText('Original sources')).toBeTruthy()
    expect(screen.getByText('Affected systems')).toBeTruthy()
    expect(screen.getByText('Related work')).toBeTruthy()

    for (const source of [
      'Slack thread - 14 messages',
      'Fathom meeting - 32 min',
      'GitHub PR #418',
      'Linear ENG-421',
      'Architecture doc',
    ]) {
      expect(screen.getAllByText(source).length).toBeGreaterThan(0)
    }

    for (const system of ['Sync engine', 'Decision graph', 'Onboarding']) {
      expect(screen.getAllByText(system).length).toBeGreaterThan(0)
    }
  })

  it('does not render the previous ticket-first hero language', () => {
    render(<Hero />)

    expect(screen.queryByText('Stop gathering context')).toBeNull()
    expect(screen.queryByText('Start shipping code')).toBeNull()
    expect(screen.queryByText('Pick a ticket')).toBeNull()
    expect(screen.queryByText('AI synthesis complete')).toBeNull()
  })
})
