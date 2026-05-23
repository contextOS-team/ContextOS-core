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
  it('renders the approved decision-memory hero copy, conversion CTA pair, microcopy, and native background', () => {
    render(<Hero />)

    expect(screen.queryByText('Early access for engineering teams')).toBeNull()
    expect(
      screen.getByRole('heading', {
        name: 'Know why your company works the way it does.',
      })
    ).toBeTruthy()
    expect(
      screen.getByText(
        'Decisions get made. The reasoning gets scattered. ContextOS reconstructs the trail across Slack, PRs, meetings, docs, and tickets, so your team can see why something exists and what source proves it.'
      )
    ).toBeTruthy()
    expect(screen.queryByText(/Decision memory for engineering teams/i)).toBeNull()

    const primaryLink = screen.getByRole('link', {
      name: 'Book a walkthrough',
    })
    expect(primaryLink.getAttribute('href')).toBe('#booking')

    const secondaryLink = screen.getByRole('link', {
      name: 'View example record',
    })
    expect(secondaryLink.getAttribute('href')).toBe('#demo')
    expect(screen.getByText('15 minutes. Bring one messy decision.')).toBeTruthy()

    expect(screen.getByTestId('hero-native-background')).toBeTruthy()
    expect(screen.queryByTestId('unicorn-scene')).toBeNull()
    expect(screen.queryByText(/Made with unicorn\.studio/i)).toBeNull()
  })

  it('keeps the detailed decision graph demo out of the hero', () => {
    render(<Hero />)

    expect(screen.queryByLabelText('DecisionGraphDemo')).toBeNull()
    expect(screen.queryByText('Decision Record')).toBeNull()
    expect(screen.queryByText('Source stream')).toBeNull()
  })

  it('does not render the previous ticket-first hero language', () => {
    render(<Hero />)

    expect(screen.queryByText('Stop gathering context')).toBeNull()
    expect(screen.queryByText('Start shipping code')).toBeNull()
    expect(screen.queryByText('Pick a ticket')).toBeNull()
    expect(screen.queryByText('AI synthesis complete')).toBeNull()
  })
})
