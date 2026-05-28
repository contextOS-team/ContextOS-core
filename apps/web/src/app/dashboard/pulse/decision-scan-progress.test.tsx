// @vitest-environment jsdom

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { MissedDecisionScanStatus } from '@/lib/api'
import { DecisionScanProgress } from './decision-scan-progress'

function scan(
  overrides: Partial<MissedDecisionScanStatus> = {}
): MissedDecisionScanStatus {
  return {
    id: 'scan-1',
    source_type: 'slack_message',
    status: 'running',
    sources_scanned: 4,
    sources_total: 10,
    progress_percent: 40,
    candidates_created: 0,
    started_at: '2026-05-25T09:00:00Z',
    completed_at: null,
    error_message: null,
    ...overrides,
  }
}

describe('DecisionScanProgress', () => {
  it('renders nothing when there are no active or recent scans', () => {
    const { container } = render(<DecisionScanProgress scans={[]} />)

    expect(container.textContent).toBe('')
  })

  it('renders queued and determinate running scan states', () => {
    const { rerender } = render(
      <DecisionScanProgress scans={[scan({ status: 'queued' })]} />
    )

    expect(screen.getByText('Waiting to scan Slack for missed decisions')).toBeTruthy()

    rerender(<DecisionScanProgress scans={[scan()]} />)

    expect(screen.getByText('Scanning Slack for missed decisions')).toBeTruthy()
    expect(screen.getByText('4 of 10 messages checked · 0 candidates so far')).toBeTruthy()
    expect(screen.getByRole('progressbar').getAttribute('aria-valuenow')).toBe('40')
  })

  it('shows candidates found during an active scan', () => {
    render(
      <DecisionScanProgress scans={[scan({ candidates_created: 2 })]} />
    )

    expect(screen.getByText('4 of 10 messages checked · 2 candidates found')).toBeTruthy()
  })

  it('renders candidate and empty completed states', () => {
    const { rerender } = render(
      <DecisionScanProgress
        scans={[scan({ status: 'succeeded', candidates_created: 3 })]}
      />
    )

    expect(screen.getByText('Found 3 candidates')).toBeTruthy()

    rerender(
      <DecisionScanProgress
        scans={[scan({ status: 'succeeded', candidates_created: 0 })]}
      />
    )

    expect(screen.getByText('No missed decisions in this scan')).toBeTruthy()
  })

  it('renders failed scans with short error copy', () => {
    render(
      <DecisionScanProgress
        scans={[
          scan({
            status: 'failed',
            error_message: 'Extractor timeout after Slack source batch finished',
          }),
        ]}
      />
    )

    expect(screen.getByText('Scan paused')).toBeTruthy()
    expect(screen.getByText('Extractor timeout after Slack source batch finished')).toBeTruthy()
  })
})
