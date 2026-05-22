// @vitest-environment jsdom

import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CTASection from '../CTASection'
import Hero from '../Hero'
import Nav from '../Nav'

const getCalApiMock = vi.hoisted(() => vi.fn(() => Promise.resolve(vi.fn())))

vi.mock('posthog-js/react', () => ({
  usePostHog: () => ({
    capture: vi.fn(),
  }),
}))

vi.mock('next/dynamic', () => ({
  default: () => function DynamicMock() {
    return <div data-testid="hero-demo" />
  },
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
  getCalApi: getCalApiMock,
}))

describe('landing booking CTA', () => {
  beforeEach(() => {
    getCalApiMock.mockClear()
  })

  it('routes primary landing CTAs to the inline booking section', () => {
    render(
      <>
        <Nav />
        <Hero />
      </>
    )

    const bookingLinks = screen.getAllByRole('link', {
      name: /see your decision graph/i,
    })

    expect(bookingLinks.length).toBeGreaterThanOrEqual(2)
    for (const link of bookingLinks) {
      expect(link.getAttribute('href')).toBe('#booking')
    }
    expect(screen.queryAllByRole('link', { name: /get early access/i })).toHaveLength(0)
  })

  it('renders an inline Cal.com booking embed for Daulet', () => {
    render(<CTASection />)

    expect(document.getElementById('booking')).toBeTruthy()
    expect(screen.getByRole('heading', {
      name: /see your decision graph from your own workspace/i,
    })).toBeTruthy()
    expect(screen.queryByPlaceholderText(/you@company\.com/i)).toBeNull()
    expect(screen.getByTestId('cal-inline').getAttribute('data-cal-link')).toBe('daulet')
    expect(screen.getByTestId('cal-inline').getAttribute('data-layout')).toBe('month_view')
    expect(screen.getByTestId('cal-inline').getAttribute('data-theme')).toBe('dark')
  })

  it('does not send Cal UI commands before the inline iframe exists', () => {
    render(<CTASection />)

    expect(getCalApiMock).not.toHaveBeenCalled()
  })
})
