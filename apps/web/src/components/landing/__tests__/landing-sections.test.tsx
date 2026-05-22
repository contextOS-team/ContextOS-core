// @vitest-environment jsdom

import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import CTASection from '../CTASection'
import Footer from '../Footer'
import Integrations from '../Integrations'
import ProductDemo from '../ProductDemo'

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
  it('renders the demo-first product proof without the old explainer stack', () => {
    render(<ProductDemo />)

    expect(screen.getByText('Ask why a ticket exists. Get the decision trail.')).toBeTruthy()
    expect(screen.getByText('Ask a decision question')).toBeTruthy()
    expect(screen.getByText('Why are we keeping source ingestion workspace-scoped?')).toBeTruthy()
    expect(screen.getByText(/keep ingestion workspace-scoped so source evidence/i)).toBeTruthy()
    expect(screen.getByText('Ticket context')).toBeTruthy()
    expect(screen.getByText('PR context')).toBeTruthy()
    expect(screen.getByText('Source-backed decisions')).toBeTruthy()
    expect(screen.getByText('Review-ready PR context')).toBeTruthy()
  })

  it('renders compact source, booking, and footer copy', () => {
    render(
      <>
        <Integrations />
        <CTASection />
        <Footer />
      </>
    )

    expect(screen.getByText('Connect the places where decisions already happen.')).toBeTruthy()
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
