// @vitest-environment jsdom

import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import LandingPage from '@/app/(landing)/page'
import CTASection from '../CTASection'
import Footer from '../Footer'
import FAQSection from '../FAQSection'
import Integrations from '../Integrations'
import UseCasesSection from '../UseCasesSection'

vi.mock('posthog-js/react', () => ({
  usePostHog: () => ({
    capture: vi.fn(),
  }),
}))

vi.mock('@/hooks/useInView', () => ({
  useInView: () => ({
    ref: { current: null },
    inView: true,
  }),
}))

vi.mock('@calcom/embed-react', () => ({
  default: ({
    calLink,
    config,
  }: {
    calLink: string
    config?: { layout?: string; theme?: string }
  }) => (
    <div
      data-testid="cal-inline"
      data-cal-link={calLink}
      data-layout={config?.layout}
      data-theme={config?.theme}
    />
  ),
}))

afterEach(() => {
  vi.useRealTimers()
})

describe('landing section rewrite', () => {
  it('renders the refined page composition with a dedicated demo and FAQ', () => {
    render(<LandingPage />)

    expect(document.getElementById('demo')).toBeTruthy()
    expect(document.getElementById('use-cases')).toBeTruthy()
    expect(document.getElementById('integrations')).toBeTruthy()
    expect(document.getElementById('faq')).toBeTruthy()
    expect(document.getElementById('booking')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'How it works' })).toBeTruthy()
    expect(screen.queryByRole('link', { name: 'Decision graph' })).toBeNull()
    expect(screen.queryByText('The Problem')).toBeNull()
    expect(screen.queryByText('How It Works')).toBeNull()
    expect(screen.queryByText('Features')).toBeNull()
    expect(screen.queryByText('Product demo')).toBeNull()
  })

  it('renders source icons feeding into a decision graph core', () => {
    vi.useFakeTimers()
    render(<LandingPage />)

    expect(screen.getByLabelText('DecisionGraphDemo')).toBeTruthy()
    expect(screen.getByText('Source matching')).toBeTruthy()
    expect(screen.getByLabelText('Sources feeding the decision graph')).toBeTruthy()
    expect(screen.getAllByText('Decision graph').length).toBeGreaterThan(0)
    expect(screen.getByText('Waiting for source agreement...')).toBeTruthy()
    expect(screen.getAllByText('Slack').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Meeting').length).toBeGreaterThan(0)
    expect(screen.getAllByText('GitHub').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Linear/Jira').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Docs').length).toBeGreaterThan(0)
    expect(screen.getByText('Decision Record')).toBeTruthy()
    expect(screen.queryByText('Graph confidence')).toBeNull()
    expect(screen.queryByText('98%')).toBeNull()
    expect(screen.queryByText('Source icons')).toBeNull()
    expect(screen.queryByText('5 feeds')).toBeNull()
    expect(screen.queryByText('Source packets')).toBeNull()
    expect(screen.queryByText('Source feed')).toBeNull()
    expect(screen.queryByText('live inputs')).toBeNull()
    expect(screen.queryByText('Enterprise data boundaries keep coming up in sales calls.')).toBeNull()

    act(() => {
      vi.advanceTimersByTime(6600)
    })

    expect(screen.getAllByText('5 sources matched').length).toBeGreaterThan(0)
    expect(screen.getByText('Verified from 5 sources')).toBeTruthy()
    expect(screen.getByText('Keep tenant isolation at database level')).toBeTruthy()
    expect(screen.getByText('Enterprise customers need strict data boundaries')).toBeTruthy()
    expect(screen.getByText('Ayan')).toBeTruthy()
    expect(screen.getByText('Madina')).toBeTruthy()
    expect(screen.getByText('Bekbol')).toBeTruthy()
    expect(screen.getByText('Slack thread')).toBeTruthy()
    expect(screen.getAllByText('PR #418').length).toBeGreaterThan(0)
    expect(screen.getByText('Architecture note')).toBeTruthy()
    expect(screen.getByText('Auth')).toBeTruthy()
    expect(screen.getByText('Billing')).toBeTruthy()
    expect(screen.getByText('Enterprise plan')).toBeTruthy()
    expect(screen.getByText('Verified')).toBeTruthy()
    expect(screen.queryByText('Evidence timeline')).toBeNull()
    expect(screen.queryByText('Current finding')).toBeNull()
    expect(screen.queryByText(/\/5/)).toBeNull()

    act(() => {
      vi.advanceTimersByTime(5700)
    })

    expect(screen.getByText('Waiting for source agreement...')).toBeTruthy()
    expect(screen.queryByText('Verified from 5 sources')).toBeNull()
    expect(screen.queryByText('Keep tenant isolation at database level')).toBeNull()
    vi.useRealTimers()
  })

  it('renders compact source, booking, and footer copy', () => {
    render(
      <>
        <UseCasesSection />
        <Integrations />
        <FAQSection />
        <CTASection />
        <Footer />
      </>
    )

    expect(screen.getByText('Source coverage')).toBeTruthy()
    expect(screen.getByText('Recover the reasoning behind real work.')).toBeTruthy()
    expect(screen.getByText('Today')).toBeTruthy()
    expect(screen.getByText('The team searches across tools by hand.')).toBeTruthy()
    expect(screen.getByText('With ContextOS')).toBeTruthy()
    expect(screen.getByText('They open a verified decision record with the rationale, people, systems, and original sources connected.')).toBeTruthy()
    expect(screen.getByText('Onboarding')).toBeTruthy()
    expect(screen.getByText('Architecture decisions')).toBeTruthy()
    expect(screen.getByText('Customer escalations')).toBeTruthy()
    expect(screen.getByText('Keep your tools. Connect the decisions inside them.')).toBeTruthy()
    expect(screen.getByText('8')).toBeTruthy()
    expect(screen.getByText('sources connected')).toBeTruthy()
    expect(screen.getByText('verified decision')).toBeTruthy()
    expect(screen.getByText('Connected now')).toBeTruthy()
    expect(screen.getByText('Queued next')).toBeTruthy()
    expect(screen.getByTitle('GitLab')).toBeTruthy()
    expect(screen.getByTitle('Fathom')).toBeTruthy()
    expect(screen.getByTitle('Google Docs')).toBeTruthy()
    expect(screen.getByTitle('Granola')).toBeTruthy()
    expect(document.getElementById('booking')).toBeTruthy()
    expect(screen.getByRole('heading', {
      name: /bring one messy decision/i,
    })).toBeTruthy()
    expect(screen.getByText("We'll map a recent decision from your workspace and show how the reasoning, people, sources, and affected systems connect.")).toBeTruthy()
    expect(screen.getAllByText(/decision memory/i).length).toBeGreaterThan(0)
    expect(screen.getByText('No migration. No perfect docs. No replacement.')).toBeTruthy()
    expect(screen.getByText('Will this replace Slack, Linear, Jira, or GitHub?')).toBeTruthy()
    expect(screen.queryByTestId('cal-inline')).toBeNull()
  })
})
