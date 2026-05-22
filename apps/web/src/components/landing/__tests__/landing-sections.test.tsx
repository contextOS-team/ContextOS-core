// @vitest-environment jsdom

import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import CTASection from '../CTASection'
import Features from '../Features'
import Footer from '../Footer'
import HowItWorks from '../HowItWorks'
import Integrations from '../Integrations'
import ProblemSection from '../ProblemSection'
import ProductDemo from '../ProductDemo'
import TrustBar from '../TrustBar'

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

describe('landing section rewrite', () => {
  it('renders the lost-decision problem and source-backed workflow copy', () => {
    render(
      <>
        <ProblemSection />
        <HowItWorks />
        <ProductDemo />
      </>
    )

    for (const question of [
      'Why was this built this way?',
      'Who decided it?',
      'What alternatives were rejected?',
      'Is it still true?',
      'Where is the source?',
    ]) {
      expect(screen.getByText(question)).toBeTruthy()
    }

    expect(screen.getByText('Connect your sources')).toBeTruthy()
    expect(screen.getByText('ContextOS detects decisions')).toBeTruthy()
    expect(screen.getByText('Use the decision graph where work happens')).toBeTruthy()
    expect(screen.getByText('Every decision comes with receipts.')).toBeTruthy()
    expect(screen.getAllByText('Original sources').length).toBeGreaterThan(0)
    expect(screen.getAllByText('People involved').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Affected systems').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Related work').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Verified').length).toBeGreaterThan(0)
  })

  it('renders MVP capability, integration, booking, and footer copy', () => {
    render(
      <>
        <Features />
        <Integrations />
        <TrustBar />
        <CTASection />
        <Footer />
      </>
    )

    expect(screen.getByText('Source-backed decisions')).toBeTruthy()
    expect(screen.getByText('Decision graph')).toBeTruthy()
    expect(screen.getByText('Context pages')).toBeTruthy()
    expect(screen.getByText(/Next: close the loop with task creation/i)).toBeTruthy()
    expect(screen.getAllByText('GitLab').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Fathom').length).toBeGreaterThan(0)
    expect(document.getElementById('booking')).toBeTruthy()
    expect(screen.getByRole('heading', {
      name: /see your decision graph from your own workspace/i,
    })).toBeTruthy()
    expect(screen.getAllByText(/decision memory/i).length).toBeGreaterThan(0)
    expect(screen.getByTestId('cal-inline').getAttribute('data-cal-link')).toBe('daulet')
  })
})
