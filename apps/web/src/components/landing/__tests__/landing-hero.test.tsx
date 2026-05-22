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
        'A source-backed decision trail for every ticket and PR: what changed, why, who decided it, and the evidence from Slack, meetings, code review, docs, and issues.'
      )
    ).toBeTruthy()
    expect(
      screen.getByText(
        'Sample workspace: Slack, Fathom, GitHub/GitLab, Linear/Jira, Notion, and Telegram.'
      )
    ).toBeTruthy()

    const primaryLink = screen.getByRole('link', {
      name: 'View product demo',
    })
    expect(primaryLink.getAttribute('href')).toBe('#demo')

    const secondaryLink = screen.getByRole('link', {
      name: 'See your decision graph',
    })
    expect(secondaryLink.getAttribute('href')).toBe('#booking')
  })

  it('keeps the hero minimal and leaves product proof to the demo section', () => {
    render(<Hero />)

    expect(screen.queryByText('Decision Receipt')).toBeNull()
    expect(screen.queryByText('Original sources')).toBeNull()
    expect(screen.queryByText('Affected systems')).toBeNull()
  })

  it('does not render the previous ticket-first hero language', () => {
    render(<Hero />)

    expect(screen.queryByText('Stop gathering context')).toBeNull()
    expect(screen.queryByText('Start shipping code')).toBeNull()
    expect(screen.queryByText('Pick a ticket')).toBeNull()
    expect(screen.queryByText('AI synthesis complete')).toBeNull()
  })
})
